import re
import json
from collections import OrderedDict


from dateutil.relativedelta import relativedelta
from django.db import models
from django.db.models import Q
from django.db.models.query import prefetch_related_objects
from django.contrib.auth.models import Group as UserGroup
from django.core.validators import EmailValidator
from django.core.validators import RegexValidator
from django.utils import timezone


from squad.core.utils import random_token, parse_name, join_name


slug_pattern = '[a-zA-Z0-9][a-zA-Z0-9_.-]*'
slug_validator = RegexValidator(regex='^' + slug_pattern)


class Group(models.Model):
    slug = models.CharField(max_length=100, unique=True, validators=[slug_validator])
    name = models.CharField(max_length=100, null=True)
    user_groups = models.ManyToManyField(UserGroup)

    def __str__(self):
        return self.slug


class ProjectManager(models.Manager):

    def accessible_to(self, user):
        if user.is_superuser:
            return self.all()
        else:
            return self.filter(Q(group__user_groups__in=user.groups.all()) | Q(is_public=True))


class Project(models.Model):
    objects = ProjectManager()

    group = models.ForeignKey(Group, related_name='projects')
    slug = models.CharField(max_length=100, validators=[slug_validator])
    name = models.CharField(max_length=100, null=True)
    is_public = models.BooleanField(default=True)

    NOTIFY_ALL_BUILDS = 'all'
    NOTIFY_ON_CHANGE = 'change'
    notification_strategy = models.CharField(
        max_length=32,
        choices=((NOTIFY_ALL_BUILDS, 'All builds'), (NOTIFY_ON_CHANGE, 'Only on change')),
        default='all'
    )

    def __init__(self, *args, **kwargs):
        super(Project, self).__init__(*args, **kwargs)
        self.__status__ = None

    @property
    def status(self):
        if not self.__status__:
            self.__status__ = Status.objects.filter(
                test_run__build__project=self, suite=None
            ).latest('test_run__datetime')
        return self.__status__

    def accessible_to(self, user):
        return self.is_public or user.is_superuser or self.group.user_groups.filter(id__in=user.groups.all()).exists()

    @property
    def full_name(self):
        return str(self.group) + '/' + self.slug

    def __str__(self):
        return self.full_name

    class Meta:
        unique_together = ('group', 'slug',)


class Token(models.Model):
    project = models.ForeignKey(Project, related_name='tokens', null=True)
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
    datetime = models.DateTimeField()

    class Meta:
        unique_together = ('project', 'version',)
        ordering = ['datetime']

    def save(self, *args, **kwargs):
        if not self.datetime:
            self.datetime = timezone.now()
        super(Build, self).save(*args, **kwargs)

    def __str__(self):
        return '%s (%s)' % (self.version, self.datetime)

    @staticmethod
    def prefetch_related(builds):
        prefetch_related_objects(
            builds,
            'project',
            'project__group',
            'test_runs',
            'test_runs__environment',
            'test_runs__tests',
            'test_runs__tests__suite',
        )

    @property
    def test_summary(self):
        summary = OrderedDict()
        summary['total'] = 0
        summary['pass'] = 0
        summary['fail'] = 0
        summary['missing'] = 0
        summary['failures'] = OrderedDict()
        mapping = {True: 'pass', False: 'fail', None: 'missing'}
        for run in self.test_runs.all():
            for test in run.tests.all():
                summary[mapping[test.result]] += 1
                summary['total'] += 1
                if not test.result and test.result is not None:
                    env = test.test_run.environment.slug
                    if env not in summary['failures']:
                        summary['failures'][env] = []
                    summary['failures'][env].append(test)
        return summary

    @property
    def metadata(self):
        """
        The build metadata is the intersection of the metadata in its test
        runs.
        """
        metadata = {}
        for test_run in self.test_runs.all():
            if metadata:
                metadata = dict_intersection(metadata, test_run.metadata)
            else:
                metadata = test_run.metadata
        return metadata

    @property
    def finished(self):
        """
        A finished build is a build that has at least N test runs for each of
        the project environments, where N is configured in
        Environment.expected_test_runs.

        If an environment does not have expected_test_runs set, or has it set to
        0, then there must be at least one test run for that environment.
        """
        environments = self.project.environments.all()
        expected = {e.id: e.expected_test_runs for e in environments}

        received = {}
        for t in self.test_runs.filter(completed=True).all():
            received.setdefault(t.environment_id, 0)
            received[t.environment_id] += 1

        for env, n in expected.items():
            if env not in received:
                return False
            if n and received[env] < n:
                return False
        return True


def dict_intersection(d1, d2):
    return {k: d1[k] for k in d1 if (k in d2 and d2[k] == d1[k])}


class Environment(models.Model):
    project = models.ForeignKey(Project, related_name='environments')
    slug = models.CharField(max_length=100, validators=[slug_validator])
    name = models.CharField(max_length=100, null=True)
    expected_test_runs = models.IntegerField(default=None, null=True)

    class Meta:
        unique_together = ('project', 'slug',)

    def __str__(self):
        return self.name or self.slug


class TestRun(models.Model):
    build = models.ForeignKey(Build, related_name='test_runs')
    environment = models.ForeignKey(Environment, related_name='test_runs')
    created_at = models.DateTimeField(auto_now_add=True)
    tests_file = models.TextField(null=True)
    metrics_file = models.TextField(null=True)
    log_file = models.TextField(null=True)
    metadata_file = models.TextField(null=True)

    completed = models.BooleanField(default=True)

    # fields that should be provided in a submitted metadata JSON
    datetime = models.DateTimeField(null=False)
    build_url = models.CharField(null=True, max_length=2048)
    job_id = models.CharField(null=True, max_length=128)
    job_status = models.CharField(null=True, max_length=128)
    job_url = models.CharField(null=True, max_length=2048)
    resubmit_url = models.CharField(null=True, max_length=2048)

    data_processed = models.BooleanField(default=False)
    status_recorded = models.BooleanField(default=False)

    class Meta:
        unique_together = ('build', 'job_id')

    def save(self, *args, **kwargs):
        if not self.datetime:
            self.datetime = timezone.now()
        super(TestRun, self).save(*args, **kwargs)

    @property
    def project(self):
        return self.build.project

    @property
    def metadata(self):
        if self.metadata_file:
            return json.loads(self.metadata_file)
        else:
            return {}

    def __str__(self):
        return self.job_id and ('#%s' % self.job_id) or ('(%s)' % self.id)


class Attachment(models.Model):
    test_run = models.ForeignKey(TestRun, related_name='attachments')
    filename = models.CharField(null=False, max_length=1024)
    data = models.BinaryField(default=None)
    length = models.IntegerField(default=None)


class Suite(models.Model):
    project = models.ForeignKey(Project, related_name='suites')
    slug = models.CharField(max_length=256, validators=[slug_validator])
    name = models.CharField(max_length=256, null=True)

    class Meta:
        unique_together = ('project', 'slug',)

    def __str__(self):
        return self.name or self.slug


class Test(models.Model):
    test_run = models.ForeignKey(TestRun, related_name='tests')
    suite = models.ForeignKey(Suite)
    name = models.CharField(max_length=256)
    result = models.NullBooleanField()

    def __str__(self):
        return "%s: %s" % (self.name, self.status)

    @property
    def status(self):
        return {True: 'pass', False: 'fail', None: 'skip/unknown'}[self.result]

    @property
    def full_name(self):
        return join_name(self.suite.slug, self.name)

    @staticmethod
    def prefetch_related(tests):
        prefetch_related_objects(
            tests,
            'test_run',
            'test_run__environment',
            'test_run__build',
        )

    class History(object):
        def __init__(self, since, count, last_different):
            self.since = since
            self.count = count
            self.last_different = last_different

    __history__ = None

    @property
    def history(self):
        if self.__history__:
            return self.__history__

        date = self.test_run.build.datetime
        previous_tests = Test.objects.filter(
            suite=self.suite,
            name=self.name,
            test_run__build__datetime__lt=date,
            test_run__environment=self.test_run.environment,
        ).exclude(id=self.id).order_by("-test_run__build__datetime")
        since = None
        count = 0
        last_different = None
        for test in list(previous_tests):
            if test.result == self.result:
                since = test
                count += 1
            else:
                last_different = test
                break
        self.__history__ = Test.History(since, count, last_different)
        return self.__history__


class MetricManager(models.Manager):

    def by_full_name(self, name):
        (suite, metric) = parse_name(name)
        return self.filter(suite__slug=suite, name=metric)


class Metric(models.Model):
    test_run = models.ForeignKey(TestRun, related_name='metrics')
    suite = models.ForeignKey(Suite)
    name = models.CharField(max_length=100)
    result = models.FloatField()
    measurements = models.TextField()  # comma-separated float numbers

    objects = MetricManager()

    @property
    def measurement_list(self):
        if self.measurements:
            return [float(n) for n in self.measurements.split(',')]
        else:
            return []

    @property
    def full_name(self):
        return join_name(self.suite.slug, self.name)

    def __str__(self):
        return '%s: %f' % (self.name, self.result)


class StatusManager(models.Manager):

    def by_suite(self):
        return self.exclude(suite=None)

    def overall(self):
        return self.filter(suite=None)


class Status(models.Model):
    test_run = models.ForeignKey(TestRun, related_name='status')
    suite = models.ForeignKey(Suite, null=True)

    tests_pass = models.IntegerField(default=0)
    tests_fail = models.IntegerField(default=0)
    metrics_summary = models.FloatField(default=0.0)

    objects = StatusManager()

    class Meta:
        unique_together = ('test_run', 'suite',)

    @property
    def total_tests(self):
        return self.tests_pass + self.tests_fail

    @property
    def pass_percentage(self):
        if self.tests_pass > 0:
            return 100 * (float(self.tests_pass) / float(self.total_tests))
        else:
            return 0

    @property
    def fail_percentage(self):
        return 100 - self.pass_percentage

    @property
    def environment(self):
        return self.test_run.environment

    @property
    def tests(self):
        return self.test_run.tests.filter(suite=self.suite)

    @property
    def metrics(self):
        return self.test_run.metrics.filter(suite=self.suite)

    @property
    def has_tests(self):
        return (self.tests_pass + self.tests_fail) > 0

    @property
    def has_metrics(self):
        return len(self.metrics) > 0

    def __str__(self):
        if self.suite:
            name = self.suite.slug + ' on ' + self.environment.slug
        else:
            name = self.environment.slug
        return '%s: %f, %d%% pass' % (name, self.metrics_summary, self.pass_percentage)


class ProjectStatus(models.Model):
    """
    Represents a "checkpoint" of a project status in time. It is used by the
    notification system to know what was the project status at the time of the
    last notification.
    """
    build = models.ForeignKey('Build', null=True)
    previous = models.ForeignKey('ProjectStatus', null=True, related_name='next')
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def create(cls, project):
        """
        Creates a new ProjectStatus, pointing to the latest finished build of
        the given project. Returns the new ProjectStatus objects.

        If there is no such build, does nothing and returns None.
        """
        previous = cls.objects.filter(build__project=project).last()

        builds = project.builds.order_by('datetime')
        if previous and previous.build:
            builds = builds.filter(datetime__gt=previous.build.datetime)

        build_list = list(builds)
        while len(build_list) > 0:
            build = build_list.pop()
            if build.finished and (not previous or (previous.build != build)):
                return cls.objects.create(build=build, previous=previous)

        return None

    @property
    def builds(self):
        """
        Returns a list of builds that happened between the previous
        ProjectStatus and this one. Can be more than one.
        """
        if not self.previous:
            return self.build.project.builds.all()
        previous = self.previous.build
        return self.build.project.builds.filter(
            datetime__gt=previous.datetime,
            datetime__lte=self.build.datetime,
        ).order_by('datetime')

    def __str__(self):
        return 'Project: %s; Build %s; created at %s' % (self.build.project, self.build, self.created_at)


class Subscription(models.Model):
    project = models.ForeignKey(Project, related_name='subscriptions')
    email = models.CharField(max_length=1024, validators=[EmailValidator()])
    html = models.BooleanField(default=True, verbose_name='Send HTML version')

    def __str__(self):
        return '%s on %s' % (self.email, self.project)
