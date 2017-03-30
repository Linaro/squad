from django.db import models


from squad.core.models import Project, slug_validator
from squad.core.fields import VersionField


from squad.ci.backend import get_backend_implementation, ALL_BACKENDS


def list_backends():
    for backend in ALL_BACKENDS:
        yield backend


class Backend(models.Model):
    url = models.URLField()
    username = models.CharField(max_length=128)
    token = models.CharField(max_length=1024)
    implementation_type = models.CharField(
        max_length=64,
        choices=list_backends(),
        default='null',
    )
    poll_interval = models.IntegerField(default=60)  # minutes

    def get_implementation(self):
        return get_backend_implementation(self)

    def __str__(self):
        return '%s (%s)' % (self.url, self.implementation_type)


class TestJob(models.Model):
    # input
    backend = models.ForeignKey(Backend, related_name='test_jobs')
    target = models.ForeignKey(Project)
    build = VersionField()
    environment = models.CharField(max_length=100, validators=[slug_validator])
    definition = models.TextField()

    # control
    submitted = models.BooleanField(default=False)
    fetched = models.BooleanField(default=False)
    last_fetch_attempt = models.DateTimeField(null=True, default=None, blank=True)

    # output
    job_id = models.CharField(null=True, max_length=128, blank=True)
    job_status = models.CharField(null=True, max_length=128, blank=True)
