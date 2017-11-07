import json
from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta


from squad.core.tasks import ReceiveTestRun
from squad.core.models import Project, Build, TestRun, slug_validator


from squad.ci.backend import get_backend_implementation, ALL_BACKENDS


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
    poll_interval = models.IntegerField(default=60)  # minutes

    def poll(self):
        for test_job in self.test_jobs.filter(submitted=True, fetched=False):
            last = test_job.last_fetch_attempt
            if last:
                now = timezone.now()
                next_poll = last + relativedelta(minutes=self.poll_interval)
                if now > next_poll:
                    yield test_job
            else:
                yield test_job

    def fetch(self, test_job):
        if not test_job.fetched:
            self.really_fetch(test_job)

    def really_fetch(self, test_job):
        implementation = self.get_implementation()
        results = implementation.fetch(test_job)

        if results:
            # create TestRun
            status, completed, metadata, tests, metrics, logs = results

            test_job.job_status = status
            if not completed:
                if tests or metrics:
                    # this means the job produced 'some' results
                    # and can be reported on
                    completed = True
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

            receive = ReceiveTestRun(test_job.target)
            testrun = receive(
                version=test_job.build,
                environment_slug=test_job.environment,
                metadata_file=json.dumps(metadata),
                tests_file=json.dumps(tests),
                metrics_file=json.dumps(metrics),
                log_file=logs,
                completed=completed,
            )
            test_job.testrun = testrun
            test_job.fetched = True

        # save test job
        test_job.last_fetch_attempt = timezone.now()
        test_job.save()

    def submit(self, test_job):
        test_job.job_id = self.get_implementation().submit(test_job)
        test_job.submitted = True
        test_job.save()

    def get_implementation(self):
        return get_backend_implementation(self)

    def __str__(self):
        return '%s (%s)' % (self.name, self.implementation_type)


class TestJob(models.Model):
    # input - internal
    backend = models.ForeignKey(Backend, related_name='test_jobs')
    # TestRun object once it's created
    testrun = models.ForeignKey(TestRun, related_name='test_jobs', null=True, blank=True)
    # definition can only be empty if the job already exists
    # in the executor.
    definition = models.TextField(null=True, blank=True)
    # name field is optional. In case of LAVA it's extrated from
    # test job definition
    name = models.CharField(max_length=256, null=True, blank=True)

    # input - for TestRun later
    target = models.ForeignKey(Project)
    build = models.CharField(max_length=100)
    target_build = models.ForeignKey(Build, related_name='test_jobs', null=True, blank=True)
    environment = models.CharField(max_length=100, validators=[slug_validator])

    # control
    submitted = models.BooleanField(default=False)
    fetched = models.BooleanField(default=False)
    last_fetch_attempt = models.DateTimeField(null=True, default=None, blank=True)
    failure = models.TextField(null=True, blank=True)

    can_resubmit = models.BooleanField(default=False)
    # this field should be set to "previous job + 1" whenever
    # resubmitting
    resubmitted_count = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        self.target_build = self.target.builds.filter(version=self.build).first()
        super(TestJob, self).save(*args, **kwargs)

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
        if self.can_resubmit:
            self.backend.get_implementation().resubmit(self)
            if self.can_resubmit:
                # in case the backend doesn't set the can_resubmit=False
                # or the resubmit call comes from api
                self.can_resubmit = False
                self.save()

    def force_resubmit(self):
        # resubmit test job not respecting any restrictions
        self.backend.get_implementation().resubmit(self)

    def __str__(self):
        return "%s/%s" % (self.backend.name, self.job_id)
