import json
import logging
import traceback
import yaml
from io import StringIO
from django.db import models, transaction, DatabaseError
from django.db.models import Q
from django.utils import timezone
from dateutil.relativedelta import relativedelta


from squad.core.tasks import ReceiveTestRun, UpdateProjectStatus
from squad.core.models import Project, Build, TestRun, slug_validator
from squad.core.plugins import get_plugin_instance
from squad.core.tasks.exceptions import InvalidMetadata, DuplicatedTestJob
from squad.ci.exceptions import FetchIssue, SubmissionIssue
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
        # Job statuses can be one of:
        #     * None
        #     * Submitted
        #     * Scheduling
        #     * Scheduled
        #     * Running
        #     * Complete
        #     * Incomplete
        #     * Canceled
        #     * Fetching
        # Only jobs in 'Complete', 'Canceled' and 'Incomplete' are eligible for fetching

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

            test_job.job_status = 'Fetching'
            test_job.fetched = True
            test_job.fetched_at = timezone.now()
            test_job.save()

        status, completed, metadata, tests, metrics, logs = results

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
        metadata['job_status'] = status
        if test_job.url is not None:
            metadata['job_url'] = test_job.url
        try:
            receive = ReceiveTestRun(test_job.target, update_project_status=False)
            testrun, _ = receive(
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

        if test_job.needs_postprocessing():
            # Offload postprocessing plugins to a new task
            test_job.save()

            # Avoids cyclic import errors
            from squad.ci.tasks import postprocess_testjob
            postprocess_testjob.delay(test_job.id, status)
        else:
            # Remove the 'Fetching' job_status only after all work is done
            test_job.update_statuses(status)

    def __postprocess_testjob__(self, test_job, job_status):
        """
        The problem

            postprocess
                plugin 1
                plugin 2
                    trigger subtasks
                plugin 3

        One ore more plugins may have subtasks, meaning that their
        main thread comes to an end before all results are in place,
        causing inconsistencies.

        The solution is to detect the count of plugins with subtasks there are
        so they can update the testjob status only at the very end
        """

        # Avoids cyclic import errors
        from squad.ci.tasks import postprocess_testjob_subtasks

        plugins = {p: get_plugin_instance(p) for p in test_job.target.enabled_plugins}
        plugins_with_subtasks = [p for p in plugins.values() if p.has_subtasks()]
        has_subtasks = len(plugins_with_subtasks) > 0

        if has_subtasks:
            # Plugins with subtasks should call squad.ci.tasks.update_testjob_status
            TestJob.set_subtasks_count(test_job.id, len(plugins_with_subtasks))

        for plugin_name, plugin in plugins.items():
            try:
                if plugin.has_subtasks():
                    postprocess_testjob_subtasks.delay(plugin_name, test_job.id, job_status)
                else:
                    plugin.postprocess_testjob(test_job)
            except Exception as e:
                logger.error("Plugin postprocessing error: " + str(e) + "\n" + traceback.format_exc())

        if not has_subtasks:
            # Remove the 'Fetching' job_status only after all work is done
            test_job.update_statuses(job_status)

    def submit(self, test_job):
        test_job.reset_build_events()
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

    def check_job_definition(self, definition):
        return self.get_implementation().check_job_definition(definition)

    def get_job_definition(self, job_id):
        return self.get_implementation().get_job_definition(job_id)

    def supports_callbacks(self):
        return self.get_implementation().supports_callbacks()

    def validate_callback(self, request, project):
        self.get_implementation().validate_callback(request, project)

    def process_callback(self, payload, build, environment):
        return self.get_implementation().process_callback(payload, build, environment, self)

    def __str__(self):
        return '%s (%s)' % (self.name, self.implementation_type)


class TestJobManager(models.Manager):

    def pending(self):
        return self.filter(Q(fetched=False) | Q(job_status='Fetching'))


class TestJob(models.Model):

    __test__ = False
    objects = TestJobManager()

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
    started_at = models.DateTimeField(null=True)
    ended_at = models.DateTimeField(null=True)

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

    # number of subtasks postprocessing this job
    subtasks_count = models.IntegerField(default=0)

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
    job_id = models.CharField(null=True, max_length=128, blank=True, db_index=True)
    job_status = models.CharField(null=True, max_length=128, blank=True)

    @property
    def url(self):
        if self.job_id is not None:
            return self.backend.get_implementation().job_url(self)
        return None

    @property
    def input(self):
        try:
            return self.results_input.text
        except ResultsInput.DoesNotExist:
            return None

    @input.setter
    def input(self, value):
        if value:
            self.results_input = ResultsInput(text=value)
            self.results_input.save()
        else:
            self.results_input.delete()

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

    def reset_build_events(self):
        # Retrigger build-finished events
        if self.target_build is not None \
           and self.target_build.status is not None \
           and self.target_build.status.finished \
           and self.target.get_setting('CI_RESET_BUILD_EVENTS_ON_JOB_RESUBMISSION', False):
            self.target_build.reset_events()

    def force_resubmit(self):
        if self.job_id is None:
            # Seems like something went wrong while submitting job in the first place
            # so just try submitting once more
            self.backend.submit(self)
            return True

        self.reset_build_events()

        # Delete old data if any
        if self.target.get_setting('CI_DELETE_RESULTS_RESUBMITTED_JOBS', False) and self.testrun:
            testrun = self.testrun
            self.testrun = None
            testrun.delete()

        success = False
        try:
            # Resubmit test job not respecting any restrictions
            self.backend.get_implementation().resubmit(self)
            self.resubmitted_count += 1

            success = True
            self.failure = None
        except SubmissionIssue as issue:
            self.failure = str(issue)

        self.save()
        return success

    def cancel(self):
        if self.job_status == "Canceled":
            return False

        if self.job_id is not None and self.backend.get_implementation().has_cancel():
            return self.backend.get_implementation().cancel(self)

        self.fetched = True
        self.submitted = True
        self.job_status = "Canceled"
        self.failure = "Canceled before submission"
        self.save()
        return True

    def needs_postprocessing(self):
        return self.testrun and self.target.enabled_plugins and any(self.target.enabled_plugins)

    def update_statuses(self, status):
        # Update this testjob's status and the build/project status assocated
        self.job_status = status
        self.save()

        if self.testrun:
            UpdateProjectStatus()(self.testrun)

    def __str__(self):
        return "%s/%s" % (self.backend.name, self.job_id)

    class Meta:
        # This index speeds up Backend.poll(), where it queries submitted and fetched together
        indexes = [
            models.Index(fields=['submitted', 'fetched']),
        ]

    @staticmethod
    def set_subtasks_count(job_id, subtasks_count):
        if subtasks_count <= 0:
            return

        with transaction.atomic():
            try:
                test_job = TestJob.objects.select_for_update(nowait=True).get(pk=job_id)
                test_job.subtasks_count = subtasks_count
                test_job.save()
            except DatabaseError:
                return

    @staticmethod
    def sub_subtasks_count(job_id):
        with transaction.atomic():
            try:
                test_job = TestJob.objects.select_for_update(nowait=True).get(pk=job_id)
                subtasks_count = test_job.subtasks_count
                if subtasks_count == 0:
                    return True

                test_job.subtasks_count -= 1
                test_job.save()
                return test_job.subtasks_count == 0
            except DatabaseError:
                return False


class ResultsInput(models.Model):
    test_job = models.OneToOneField(TestJob, related_name='results_input', on_delete=models.CASCADE, null=True)
    text = models.TextField(null=True, blank=True)
