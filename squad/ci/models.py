import json
from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta


from squad.core.tasks import ReceiveTestRun
from squad.core.models import Project, slug_validator
from squad.core.fields import VersionField


from squad.ci.backend import get_backend_implementation, ALL_BACKENDS


def list_backends():
    for backend in ALL_BACKENDS:
        yield backend


class Backend(models.Model):
    name = models.CharField(max_length=128, unique=True)
    url = models.URLField()
    # listener_url is used by backend's listen() method
    listener_url = models.URLField(null=True, blank=True)
    # listener_filter might be used by backend to filter out
    # unwanted messages
    listener_filter = models.CharField(max_length=1024, null=True, blank=True)
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
            self.fetch(test_job)

    def fetch(self, test_job):
        last = test_job.last_fetch_attempt
        if last:
            now = timezone.now()
            next_poll = last + relativedelta(minutes=self.poll_interval)
            if now > next_poll:
                self.really_fetch(test_job)
        else:
            self.really_fetch(test_job)

    def really_fetch(self, test_job):
        implementation = self.get_implementation()
        results = implementation.fetch(test_job)

        if results:
            # create TestRun
            status, metadata, tests, metrics = results

            test_job.job_status = status

            metadata['job_id'] = test_job.job_id
            metadata['job_status'] = test_job.job_status

            receive = ReceiveTestRun(test_job.target)
            receive(
                version=test_job.build,
                environment_slug=test_job.environment,
                metadata=json.dumps(metadata),
                tests_file=json.dumps(tests),
                metrics_file=json.dumps(metrics),
            )
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
    definition = models.TextField()

    # input - for TestRun later
    target = models.ForeignKey(Project)
    build = VersionField()
    environment = models.CharField(max_length=100, validators=[slug_validator])

    # control
    submitted = models.BooleanField(default=False)
    fetched = models.BooleanField(default=False)
    last_fetch_attempt = models.DateTimeField(null=True, default=None, blank=True)
    failure = models.TextField(null=True, blank=True)

    def success(self):
        return not self.failure
    success.boolean = True

    # output
    job_id = models.CharField(null=True, max_length=128, blank=True)
    job_status = models.CharField(null=True, max_length=128, blank=True)
