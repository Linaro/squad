from django.db import models
from django.contrib.auth.models import Group as UserGroup

from squad.core.utils import random_token


class Group(models.Model):
    slug = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100, null=True)
    user_groups = models.ManyToManyField(UserGroup)

    def __str__(self):
        return self.name or self.slug


class Project(models.Model):
    group = models.ForeignKey(Group, related_name='projects')
    slug = models.CharField(max_length=100)
    name = models.CharField(max_length=100, null=True)

    def __str__(self):
        return self.name or self.slug

    class Meta:
        unique_together = ('group', 'slug',)


class Token(models.Model):
    project = models.ForeignKey(Project, related_name='tokens')
    key = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=100)

    def save(self, **kwargs):
        if not self.key:
            self.key = random_token(64)
        super(Token, self).save(**kwargs)

    def __str__(self):
        return self.description


class Build(models.Model):
    project = models.ForeignKey(Project, related_name='builds')
    version = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('project', 'version',)


class Environment(models.Model):
    project = models.ForeignKey(Project, related_name='environments')
    slug = models.CharField(max_length=100)
    name = models.CharField(max_length=100, null=True)

    class Meta:
        unique_together = ('project', 'slug',)


class TestRun(models.Model):
    build = models.ForeignKey(Build, related_name='test_runs')
    environment = models.ForeignKey(Environment, related_name='test_runs')
    created_at = models.DateTimeField(auto_now_add=True)
    tests_file = models.TextField(null=True)
    benchmarks_file = models.TextField(null=True)
    log_file = models.TextField(null=True)


class Suite(models.Model):
    project = models.ForeignKey(Project, related_name='suites')
    slug = models.CharField(max_length=100)
    name = models.CharField(max_length=100, null=True)

    class Meta:
        unique_together = ('project', 'slug',)


class Test(models.Model):
    test_run = models.ForeignKey(TestRun, related_name='tests')
    suite = models.ForeignKey(Suite)
    result = models.BooleanField()


class Benchmark(models.Model):
    test_run = models.ForeignKey(TestRun, related_name='benchmarks')
    suite = models.ForeignKey(Suite)
    result = models.FloatField()
    measurements = models.TextField()  # comma-separated float numbers

    @property
    def measurement_list(self):
        [float(n) for n in self.measurements.split(',')]
