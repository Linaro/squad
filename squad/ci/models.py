import json
import logging
import traceback
import yaml
from io import StringIO
from django.db import models, transaction, DatabaseError
from django.utils import timezone
from dateutil.relativedelta import relativedelta


from squad.core.tasks import ReceiveTestRun, UpdateProjectStatus
from squad.core.models import Project, Build, TestRun, slug_validator
from squad.core.plugins import apply_plugins
from squad.core.tasks.exceptions import InvalidMetadata, DuplicatedTestJob
from squad.ci.exceptions import FetchIssue
from squad.core.utils import yaml_validator


from squad.ci.backend import get_backend_implementation, ALL_BACKENDS


logger = logging.getLogger()


def list_backends():
    for backend in ALL_BACKENDS:
        yield backend


class Backend(models.Model):
    name = models.CharField(max_length=128, unique=True)
    url = models.URLField()
    username = models.CharField(max_length=128)
    token = models.CharField(max_length=1024)
    implementation_type = models.CharField(
        max_length=64,
        choices=list_backends(),
        default='null',
    )
    backend_settings = models.TextField(
        null=True,
        blank=True,
        validators=[yaml_validator]
    )
    poll_interval = models.IntegerField(default=60)  # minutes
    max_fetch_attempts = models.IntegerField(default=3)
    poll_enabled = models.BooleanField(default=True)
    listen_enabled = models.BooleanField(default=True)

    def poll(self):
        if not self.poll_enabled:
            return
        test_jobs = self.test_jobs.filter(
            submitted=True,
            fetched=False,
            fetch_attempts__lt=self.max_fetch_attempts
        )
        for test_job in test_jobs:
            last = test_job.last_fetch_attempt
            if last:
                now = timezone.now()
                next_poll = last + relativedelta(minutes=self.poll_interval)
                if now > next_poll:
                    yield test_job
            else:
                yield test_job

    def fetch(self, job_id):
        with transaction.atomic():
            try:
                test_job = TestJob.objects.select_for_update(nowait=True).get(pk=job_id)
                if test_job.fetched or test_job.fetch_attempts >= test_job.backend.max_fetch_attempts:
                    return
            except DatabaseError:
                # another thread is working on this testjob
                return

            try:
                test_job.last_fetch_attempt = timezone.now()
                results = self.get_implementation().fetch(test_job)
                if results is None:
                    # empty results mean the job is still in progress
                    # or in the queue
                    test_job.save()
                    return
            except FetchIssue as issue:
                logger.warning("error fetching job %s: %s" % (test_job.id, str(issue)))
                test_job.failure = str(issue)
                test_job.fetched = not issue.retry
                test_job.fetch_attempts += 1
                test_job.save()
                return

            test_job.fetched = True
            test_job.fetched_at = timezone.now()
            test_job.save()

        status, completed, metadata, tests, metrics, logs = results

        test_job.job_status = status
        if not completed:
            tests = {}
            metrics = {}
            test_job.can_resubmit = True

        if completed and not tests and not metrics:
            # test job produced no results
            # mark it incomplete
            completed = False
            test_job.can_resubmit = True

        metadata['job_id'] = test_job.job_id
        metadata['job_status'] = test_job.job_status
        if test_job.url is not None:
            metadata['job_url'] = test_job.url

        try:
            receive = ReceiveTestRun(test_job.target, update_project_status=False)
            testrun = receive(
                version=test_job.target_build.version,
                environment_slug=test_job.environment,
                metadata_file=json.dumps(metadata),
                tests_file=json.dumps(tests),
                metrics_file=json.dumps(metrics),
                log_file=logs,
                completed=completed,
            )
            test_job.testrun = testrun
        except InvalidMetadata as exception:
            test_job.failure = str(exception)
        except DuplicatedTestJob as exception:
            logger.error('Failed to fetch test_job(%d): "%s"' % (test_job.id, str(exception)))

        test_job.save()

        if test_job.testrun:
            self.__postprocess_testjob__(test_job)
            UpdateProjectStatus()(test_job.testrun)

    def __postprocess_testjob__(self, test_job):
        project = test_job.target
        for plugin in apply_plugins(project.enabled_plugins):
            try:
                plugin.postprocess_testjob(test_job)
            except Exception as e:
                logger.error("Plugin postprocessing error: " + str(e) + "\n" + traceback.format_exc())

    def submit(self, test_job):
        job_id_list = self.get_implementation().submit(test_job)
        test_job.job_id = job_id_list[0]
        test_job.submitted = True
        test_job.submitted_at = timezone.now()
        test_job.save()
        if job_id_list is not None and len(job_id_list) > 1:
            # clone test job in case of multinode
            for job_id in job_id_list[1:]:
                test_job.pk = None  # according to django docs this will create new object
                test_job.job_id = job_id
                test_job.save()

    def get_implementation(self):
        return get_backend_implementation(self)

    def __str__(self):
        return '%s (%s)' % (self.name, self.implementation_type)


class TestJob(models.Model):

    __test__ = False

    # input - internal
    backend = models.ForeignKey(Backend, related_name='test_jobs', on_delete=models.CASCADE)
    # TestRun object once it's created
    testrun = models.ForeignKey(TestRun, related_name='test_jobs', null=True, blank=True, on_delete=models.CASCADE)
    # definition can only be empty if the job already exists
    # in the executor.
    definition = models.TextField(null=True, blank=True)
    # name field is optional. In case of LAVA it's extrated from
    # test job definition
    name = models.CharField(max_length=256, null=True, blank=True)

    # input - for TestRun later
    target = models.ForeignKey(Project, on_delete=models.CASCADE)
    target_build = models.ForeignKey(Build, related_name='test_jobs', null=True, blank=True, on_delete=models.CASCADE)
    environment = models.CharField(max_length=100, validators=[slug_validator])

    # dates
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    submitted_at = models.DateTimeField(null=True)
    fetched_at = models.DateTimeField(null=True)

    # control
    submitted = models.BooleanField(default=False)
    fetched = models.BooleanField(default=False)
    fetch_attempts = models.IntegerField(default=0)
    last_fetch_attempt = models.DateTimeField(null=True, default=None, blank=True)
    failure = models.TextField(null=True, blank=True)

    can_resubmit = models.BooleanField(default=False)
    # this field should be set to "previous job + 1" whenever
    # resubmitting
    resubmitted_count = models.IntegerField(default=0)
    # reference to the job that was used as base for resubmission
    parent_job = models.ForeignKey('self', default=None, blank=True, null=True, related_name="resubmitted_jobs", on_delete=models.CASCADE)

    @property
    def show_definition(self):
        try:
            # we'll loose comments in web UI
            yaml_def = yaml.safe_load(self.definition)
        except (yaml.parser.ParserError, yaml.scanner.ScannerError):
            # in case yaml is not valid, return original string
            return self.definition
        if not isinstance(yaml_def, dict):
            return yaml_def
        if 'secrets' in yaml_def.keys():
            # prevent displaying 'secrets' in the web UI
            for key, value in yaml_def['secrets'].items():
                yaml_def['secrets'][key] = "****"
        stream = StringIO()
        yaml.dump(yaml_def, stream, default_flow_style=False, allow_unicode=True, encoding=None)
        return stream.getvalue()

    def success(self):
        return not self.failure
    success.boolean = True

    # output
    job_id = models.CharField(null=True, max_length=128, blank=True)
    job_status = models.CharField(null=True, max_length=128, blank=True)

    @property
    def url(self):
        if self.job_id is not None:
            return self.backend.get_implementation().job_url(self)
        return None

    def resubmit(self):
        ret_value = False
        if self.can_resubmit:
            ret_value = self.force_resubmit()
            if self.can_resubmit:
                # in case the backend doesn't set the can_resubmit=False
                # or the resubmit call comes from api
                self.can_resubmit = False
                self.save()
        return ret_value

    def force_resubmit(self):
        # resubmit test job not respecting any restrictions
        self.backend.get_implementation().resubmit(self)
        self.resubmitted_count += 1
        self.save()
        return True

    def cancel(self):
        if self.job_id is not None:
            return self.backend.get_implementation().cancel(self)
        else:
            self.fetched = True
            self.submitted = True
            self.job_status = "Canceled"
            self.failure = "Cancelled before submission"
            self.save()
        return self.fetched

    def __str__(self):
        return "%s/%s" % (self.backend.name, self.job_id)
