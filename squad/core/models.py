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
from squad.core.statistics import geomean


slug_pattern = '[a-zA-Z0-9][a-zA-Z0-9_.-]*'
slug_validator = RegexValidator(regex='^' + slug_pattern)


class Group(models.Model):
    slug = models.CharField(max_length=100, unique=True, validators=[slug_validator])
    name = models.CharField(max_length=100, null=True)
    user_groups = models.ManyToManyField(UserGroup)

    def __str__(self):
        return self.slug

    class Meta:
        ordering = ['slug']


class ProjectManager(models.Manager):

    def accessible_to(self, user):
        if user.is_superuser:
            return self.all()
        else:
            groups = Group.objects.filter(user_groups__in=user.groups.all())
            group_ids = [g['id'] for g in groups.values('id')]
            return self.filter(Q(group_id__in=group_ids) | Q(is_public=True))


class EmailTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    subject = models.CharField(max_length=1024, null=True, blank=True, help_text='Jinja2 template for subject (single line)')
    plain_text = models.TextField(help_text='Jinja2 template for text/plain content')
    html = models.TextField(blank=True, null=True, help_text='Jinja2 template for text/html content')

    def __str__(self):
        return self.name


class Project(models.Model):
    objects = ProjectManager()

    group = models.ForeignKey(Group, related_name='projects')
    slug = models.CharField(max_length=100, validators=[slug_validator])
    name = models.CharField(max_length=100, null=True)
    is_public = models.BooleanField(default=True)
    html_mail = models.BooleanField(default=True)
    moderate_notifications = models.BooleanField(default=False)
    custom_email_template = models.ForeignKey(EmailTemplate, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

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
            self.__status__ = ProjectStatus.objects.filter(
                build__project=self
            ).latest('created_at')
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
        ordering = ['group', 'slug']


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
        return TestSummary(self)

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

    @property
    def test_runs_total(self):
        return len(self.test_runs.all())

    @property
    def test_runs_completed(self):
        return sum([1 for t in self.test_runs.all() if t.completed])

    @property
    def test_runs_incomplete(self):
        return sum([1 for t in self.test_runs.all() if not t.completed])

    @property
    def test_suites_by_environment(self):
        test_runs = self.test_runs.prefetch_related(
            'tests',
            'tests__suite',
            'environment',
        )
        result = OrderedDict()
        envlist = set([t.environment for t in test_runs])
        for env in sorted(envlist, key=lambda env: env.slug):
            result[env] = set()
        for tr in test_runs:
            for t in tr.tests.all():
                result[tr.environment].add(t.suite)
        for env in result.keys():
            result[env] = sorted(result[env], key=lambda suite: suite.slug)
        return result


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
        if self.__metadata__:
            self.metadata_file = json.dumps(self.__metadata__)
        super(TestRun, self).save(*args, **kwargs)

    @property
    def project(self):
        return self.build.project

    __metadata__ = None

    @property
    def metadata(self):
        if self.__metadata__ is None:
            if self.metadata_file:
                self.__metadata__ = json.loads(self.metadata_file)
            else:
                self.__metadata__ = {}
        return self.__metadata__

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
        return {True: 'pass', False: 'fail', None: 'skip'}[self.result]

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

    class Meta:
        ordering = ['name']


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


class TestSummaryBase(object):

    @property
    def tests_total(self):
        return self.tests_pass + self.tests_fail + self.tests_skip

    def __percent__(self, ntests):
        if ntests > 0:
            return 100 * (float(ntests) / float(self.tests_total))
        else:
            return 0

    @property
    def pass_percentage(self):
        return self.__percent__(self.tests_pass)

    @property
    def fail_percentage(self):
        return self.__percent__(self.tests_fail)

    @property
    def skip_percentage(self):
        return self.__percent__(self.tests_skip)

    @property
    def has_tests(self):
        return self.tests_total > 0


class Status(models.Model, TestSummaryBase):
    test_run = models.ForeignKey(TestRun, related_name='status')
    suite = models.ForeignKey(Suite, null=True)

    tests_pass = models.IntegerField(default=0)
    tests_fail = models.IntegerField(default=0)
    tests_skip = models.IntegerField(default=0)
    metrics_summary = models.FloatField(default=0.0)

    objects = StatusManager()

    class Meta:
        unique_together = ('test_run', 'suite',)

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
    def has_metrics(self):
        return len(self.metrics) > 0

    def __str__(self):
        if self.suite:
            name = self.suite.slug + ' on ' + self.environment.slug
        else:
            name = self.environment.slug
        return '%s: %f, %d%% pass' % (name, self.metrics_summary, self.pass_percentage)


class ProjectStatus(models.Model, TestSummaryBase):
    """
    Represents a "checkpoint" of a project status in time. It is used by the
    notification system to know what was the project status at the time of the
    last notification.
    """
    build = models.OneToOneField('Build', related_name='status')
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(null=True)
    finished = models.BooleanField(default=False)
    notified = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)

    metrics_summary = models.FloatField()
    has_metrics = models.BooleanField(default=False)

    tests_pass = models.IntegerField()
    tests_fail = models.IntegerField()
    tests_skip = models.IntegerField()

    class Meta:
        verbose_name_plural = "Project statuses"

    @classmethod
    def create_or_update(cls, build):
        """
        Creates (or updates) a new ProjectStatus for the given build and
        returns it.
        """

        test_summary = build.test_summary
        metrics_summary = MetricsSummary(build)
        now = timezone.now()
        data = {
            'tests_pass': test_summary.tests_pass,
            'tests_fail': test_summary.tests_fail,
            'tests_skip': test_summary.tests_skip,
            'metrics_summary': metrics_summary.value,
            'has_metrics': metrics_summary.has_metrics,
            'last_updated': now,
            'finished': build.finished,
        }

        status, created = cls.objects.get_or_create(build=build, defaults=data)
        if not created:
            status.tests_pass = test_summary.tests_pass
            status.tests_fail = test_summary.tests_fail
            status.tests_skip = test_summary.tests_skip
            status.metrics_summary = metrics_summary.value
            status.has_metrics = metrics_summary.has_metrics
            status.last_updated = now
            status.finished = build.finished
            status.build = build
            status.save()
        return status

    def __str__(self):
        return "%s, build %s" % (self.build.project, self.build.version)

    def get_previous(self):
        return ProjectStatus.objects.filter(
            finished=True,
            build__datetime__lt=self.build.datetime,
            build__project=self.build.project,
        ).order_by('build__datetime').last()


class TestSummary(TestSummaryBase):
    def __init__(self, build):
        self.tests_pass = 0
        self.tests_fail = 0
        self.tests_skip = 0
        self.failures = OrderedDict()

        tests = {}
        test_runs = build.test_runs.prefetch_related(
            'environment',
            'tests',
            'tests__suite'
        ).order_by('id')

        for run in test_runs.all():
            for test in run.tests.all():
                tests[(run.environment, test.suite, test.name)] = test

        for context, test in tests.items():
            if test.result is True:
                self.tests_pass += 1
            elif test.result is False:
                self.tests_fail += 1
            else:
                self.tests_skip += 1
            if not test.result and test.result is not None:
                env = test.test_run.environment.slug
                if env not in self.failures:
                    self.failures[env] = []
                self.failures[env].append(test)


class MetricsSummary(object):

    def __init__(self, build):
        metrics = Metric.objects.filter(test_run__build_id=build.id).all()
        values = [m.result for m in metrics]
        self.value = geomean(values)
        self.has_metrics = len(values) > 0


class Subscription(models.Model):
    project = models.ForeignKey(Project, related_name='subscriptions')
    email = models.CharField(max_length=1024, validators=[EmailValidator()])

    def __str__(self):
        return '%s on %s' % (self.email, self.project)


class AdminSubscription(models.Model):
    project = models.ForeignKey(Project, related_name='admin_subscriptions')
    email = models.CharField(max_length=1024, validators=[EmailValidator()])

    def __str__(self):
        return '%s on %s' % (self.email, self.project)
