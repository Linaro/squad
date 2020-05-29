import json
import yaml
from collections import OrderedDict
from hashlib import sha1
import re


from django.db import models
from django.db import transaction
from django.db.models import Q, Count, Sum, Case, When, F, Value
from django.db.models.functions import Concat
from django.db.models.query import prefetch_related_objects
from django.contrib.auth.models import User, AnonymousUser
from django.conf import settings
from squad.mail import Message
from django.forms.fields import URLField as FormURLField
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, URLValidator
from django.core.validators import RegexValidator, MaxValueValidator, MinValueValidator
from django.utils import timezone
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy as N_
from simple_history.models import HistoricalRecords

from squad.core.utils import parse_name, join_name, yaml_validator, jinja2_validator
from squad.core.utils import encrypt, decrypt, split_list
from squad.core.comparison import TestComparison
from squad.core.statistics import geomean
from squad.core.plugins import Plugin
from squad.core.plugins import PluginListField
from squad.core.plugins import PluginField
from squad.core.plugins import get_plugin_instance


slug_pattern = '[a-zA-Z0-9][a-zA-Z0-9_.-]*'
slug_validator = RegexValidator(regex='^' + slug_pattern + '$')
group_slug_pattern = '~?' + slug_pattern
group_slug_validator = RegexValidator(regex='^' + group_slug_pattern + '$')


class GroupManager(models.Manager):

    def accessible_to(self, user):
        if user.is_superuser:
            return self.all().order_by('slug').annotate(project_count=Count('projects'))
        projects = Project.objects.accessible_to(user)
        project_ids = [p.id for p in projects]
        group_ids = set([p.group_id for p in projects])
        if not isinstance(user, AnonymousUser):
            group_ids = group_ids | set([g.id for g in Group.objects.filter(members__in=[user])])
        return self.filter(
            id__in=group_ids
        ).distinct().order_by('slug').annotate(
            project_count=Sum(
                Case(
                    When(projects__id__in=project_ids, then=1),
                    default=0,
                    output_field=models.IntegerField(),
                )
            )
        )


class DisplayName(object):

    @property
    def display_name(self):
        return self.name or self.slug


class Group(models.Model, DisplayName):
    objects = GroupManager()

    slug = models.CharField(max_length=100, unique=True, validators=[group_slug_validator], db_index=True, verbose_name=N_('Slug'))
    valid_slug_pattern = slug_pattern
    name = models.CharField(max_length=100, null=True, blank=True, verbose_name=N_('Name'))
    description = models.TextField(null=True, blank=True, verbose_name=N_('Description'))
    members = models.ManyToManyField(User, through='GroupMember', verbose_name=N_('Members'))

    def add_user(self, user, access=None):
        member = GroupMember(group=self, user=user)
        if access:
            member.access = access
        member.save()

    def add_admin(self, user):
        self.add_user(user, 'admin')

    def accessible_to(self, user):
        return GroupMember.objects.filter(group=self, user=user.id).exists() or self.writable_by(user)

    def can_submit(self, user):
        return user.is_superuser or user.is_staff or self.has_access(user, 'admin', 'submitter')

    def writable_by(self, user):
        return user.is_superuser or user.is_staff or self.has_access(user, 'admin')

    def has_access(self, user, *access_levels):
        return GroupMember.objects.filter(
            group=self,
            user=user.id,
            access__in=access_levels
        ).exists()

    def __str__(self):
        return self.slug

    def full_clean(self, **kwargs):
        errors = {}
        try:
            super().full_clean(**kwargs)
        except ValidationError as e:
            errors = e.update_error_dict(errors)
        if self.slug and not re.match(self.valid_slug_pattern, self.slug):
            errors['slug'] = [_('Enter a valid value.')]
        if errors:
            raise ValidationError(errors)

    class Meta:
        ordering = ['slug']


class GroupMember(models.Model):
    ACCESS_LEVELS = (
        ('member', N_('Member')),
        ('submitter', N_('Result submitter')),
        ('admin', N_('Administrator')),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    access = models.CharField(max_length=10, choices=ACCESS_LEVELS, default='member')
    member_since = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'user')
        verbose_name = N_('Group member')
        verbose_name_plural = N_('Group members')


class UserNamespaceManager(models.Manager):

    @transaction.atomic
    def create_for(self, user):
        slug = '~' + user.username
        ns = self.create(slug=slug)
        ns.add_admin(user)
        return ns

    def get_queryset(self):
        return super().get_queryset().filter(slug__startswith='~')

    def get_for(self, user):
        return self.get(slug='~' + user.username)

    def get_or_create_for(self, user):
        try:
            return self.get_for(user)
        except self.model.DoesNotExist:
            return self.create_for(user)


class UserNamespace(Group):

    """
    A user namespace is just like a regular group. The only difference is that,
    when created with UserNamespace.objects.create_for, it sets up the given
    user as owner of the group, and adds `~` to the front of the group slug.
    """

    objects = UserNamespaceManager()
    valid_slug_pattern = group_slug_pattern

    class Meta:
        proxy = True


class ProjectManager(models.Manager):

    def accessible_to(self, user):
        if user.is_superuser or user.is_staff:
            return self.all()
        else:
            groups = Group.objects.filter(members__id=user.id).only('id')
            return self.filter(Q(group__in=groups) | Q(is_public=True))


class EmailTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    subject = models.CharField(
        max_length=1024,
        null=True,
        blank=True,
        help_text=N_('Jinja2 template for subject (single line)'),
        validators=[jinja2_validator])
    plain_text = models.TextField(help_text=N_('Jinja2 template for text/plain content'), validators=[jinja2_validator])
    html = models.TextField(blank=True, null=True, help_text=N_('Jinja2 template for text/html content'), validators=[jinja2_validator])

    # If any of the attributes need not to be tracked, just pass excluded_fields=['attr']
    history = HistoricalRecords(cascade_delete_history=True)

    def __str__(self):
        return self.name


class Project(models.Model, DisplayName):
    objects = ProjectManager()

    group = models.ForeignKey(Group, related_name='projects', on_delete=models.CASCADE)
    slug = models.CharField(max_length=100, validators=[slug_validator], db_index=True, verbose_name=N_('Slug'))
    name = models.CharField(max_length=100, null=True, blank=True, verbose_name=N_('Name'))
    is_public = models.BooleanField(default=True, verbose_name=N_('Is public'))
    html_mail = models.BooleanField(default=True)
    moderate_notifications = models.BooleanField(default=False)
    custom_email_template = models.ForeignKey(EmailTemplate, null=True, blank=True, on_delete=models.CASCADE)
    description = models.TextField(null=True, blank=True, verbose_name=N_('Description'))
    important_metadata_keys = models.TextField(null=True, blank=True)
    enabled_plugins_list = PluginListField(
        null=True,
        blank=True,
        features=[
            Plugin.postprocess_testrun,
            Plugin.postprocess_testjob,
        ],
    )

    wait_before_notification = models.IntegerField(
        help_text=N_('Wait this many seconds before sending notifications'),
        null=True,
        blank=True,
    )
    notification_timeout = models.IntegerField(
        help_text=N_('Force sending build notifications after this many seconds'),
        null=True,
        blank=True,
    )

    data_retention_days = models.IntegerField(
        default=0,
        help_text=N_("Delete builds older than this number of days. Set to 0 or any negative number to disable."),
    )

    project_settings = models.TextField(
        null=True,
        blank=True,
        validators=[yaml_validator]
    )

    is_archived = models.BooleanField(
        default=False,
        help_text=N_('Makes the project hidden from the group page by default'),
        verbose_name=N_('Is archived'),
    )

    def __init__(self, *args, **kwargs):
        super(Project, self).__init__(*args, **kwargs)
        self.__status__ = None

    @property
    def status(self):
        if not self.__status__:
            try:
                self.__status__ = ProjectStatus.objects.filter(
                    build__project=self
                ).latest('created_at')
            except ProjectStatus.DoesNotExist:
                pass
        return self.__status__

    def accessible_to(self, user):
        return self.is_public or self.group.accessible_to(user)

    def can_submit(self, user):
        return self.group.can_submit(user)

    def writable_by(self, user):
        return self.group.writable_by(user)

    def is_subscribed(self, user):
        if self.subscriptions.filter(user=user):
            return True
        return False

    @property
    def full_name(self):
        return str(self.group) + '/' + self.slug

    def __str__(self):
        return self.full_name

    class Meta:
        unique_together = ('group', 'slug',)
        ordering = ['group', 'slug']

    @property
    def enabled_plugins(self):
        return self.enabled_plugins_list


# URLField uses URLValidator which supports only http(s) and ftp(s)
# ref: https://github.com/django/django/pull/1717#issuecomment-25830269
__default_url_validator__ = [URLValidator(schemes=URLValidator().schemes + ['ssh'])]


class CustomURLFormField(FormURLField):
    default_validators = __default_url_validator__


class CustomURLField(models.URLField):
    default_validators = __default_url_validator__

    def formfield(self, **kwargs):
        return super(CustomURLField, self).formfield(**{
            'form_class': CustomURLFormField,
        })


class PatchSource(models.Model):
    """
    A patch is source is a platform from where a patch comes from, e.g. github,
    a gitlab instance, a gerrit instance. The *implementation* field specifies
    which plugin should handle the implementation details for that given patch
    source.
    """
    name = models.CharField(max_length=256, unique=True)
    username = models.CharField(max_length=128)
    _password = models.CharField(max_length=128, null=True, blank=True, db_column="password")
    url = CustomURLField(help_text="scheme://host, ex: 'http://github.com', 'ssh://gerrit.host, etc'")
    token = models.CharField(max_length=1024, blank=True)
    implementation = PluginField(
        default='null',
        features=[
            Plugin.notify_patch_build_created,
            Plugin.notify_patch_build_finished,
        ],
    )

    def get_password(self):
        if self._password:
            return decrypt(self._password)
        return None

    def set_password(self, new_password):
        self._password = encrypt(new_password)

    password = property(get_password, set_password)

    def get_implementation(self):
        return get_plugin_instance(self.implementation)

    def __str__(self):
        return 'PatchSource %s (%s)' % (self.name, self.implementation)


class Build(models.Model):
    project = models.ForeignKey(Project, related_name='builds', on_delete=models.CASCADE)
    version = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    datetime = models.DateTimeField()

    patch_source = models.ForeignKey(PatchSource, null=True, blank=True, on_delete=models.CASCADE)
    patch_baseline = models.ForeignKey('Build', null=True, blank=True, on_delete=models.CASCADE)
    patch_id = models.CharField(max_length=1024, null=True, blank=True)

    keep_data = models.BooleanField(
        default=False,
        help_text="Keep this build data even after the project data retention period has passed"
    )

    class Meta:
        unique_together = ('project', 'version',)
        ordering = ['datetime']

    def save(self, *args, **kwargs):
        if not self.datetime:
            self.datetime = timezone.now()
        with transaction.atomic():
            super(Build, self).save(*args, **kwargs)
            ProjectStatus.objects.get_or_create(build=self)

    def __str__(self):
        return '%s (%s)' % (self.version, self.datetime)

    def prefetch(self, *related):
        prefetch_related_objects([self], *related)

    @property
    def test_summary(self):
        return TestSummary(self)

    __metadata__ = None

    @property
    def metadata(self):
        """
        The build metadata is the union of the metadata in its test runs.
        Common keys with different values are transformed into a list with each
        of the different values.
        """
        if self.__metadata__ is None:
            metadata = {}
            for test_run in self.test_runs.defer(None).all():
                for key, value in test_run.metadata.items():
                    metadata.setdefault(key, [])
                    if value not in metadata[key]:
                        metadata[key].append(value)
            for key in metadata.keys():
                if len(metadata[key]) == 1:
                    metadata[key] = metadata[key][0]
                else:
                    metadata[key] = sorted(metadata[key], key=str)
            self.__metadata__ = metadata
        return self.__metadata__

    @property
    def important_metadata(self):
        wanted = (self.project.important_metadata_keys or '').splitlines()
        m = self.metadata
        if len(wanted):
            return {k: m[k] for k in wanted if k in m}
        else:
            return self.metadata

    @property
    def has_extra_metadata(self):
        if set(self.important_metadata.keys()) == set(self.metadata.keys()):
            return False
        return True

    @property
    def finished(self):
        """
        A finished build is a build that satisfies one of the following conditions:

        * it has no pending CI test jobs.
        * it has no submitted CI test jobs, and has at least N test runs for each of
          the project environments, where N is configured in
          Environment.expected_test_runs. Environment.expected_test_runs is
          interpreted as follows:

            * None (empty):  there must be at least one test run for that
              environment.
            * 0: the environment is ignored, i.e. any amount of test runs will
              be ok, including 0.
            * N > 0: at least N test runs are expected for that environment

        """
        reasons = []

        # XXX note that by using test_jobs here, we are adding an implicit
        # dependency on squad.ci, what in theory violates our architecture.
        testjobs = self.test_jobs
        if testjobs.count() > 0:
            if testjobs.filter(fetched=False).count() > 0:
                # a build that has pending CI jobs is NOT finished
                reasons.append("There are unfinished CI jobs")
            else:
                # carry on, and check whether the number of expected test runs
                # per environment is satisfied.
                pass
        elif self.test_runs.count() == 0:
            reasons.append("There are no testjobs or testruns for the build")

        # builds with no CI jobs are finished when each environment has
        # received the expected amount of test runs
        testruns = {
            e.id: {
                'name': str(e),
                'expected': e.expected_test_runs,
                'received': 0
            }
            for e in self.project.environments.all()
        }

        for t in self.test_runs.filter(completed=True).all():
            testruns[t.environment_id]['received'] += 1

        for env, count in testruns.items():
            expected = count['expected']
            received = count['received']
            env_name = count['name']
            if expected and expected > 0:
                if received == 0:
                    reasons.append("No test runs for %s received so far" % env_name)
                elif received < expected:
                    reasons.append(
                        "%d test runs expected for %s, but only %d received so far" % (
                            expected,
                            env_name,
                            received,
                        )
                    )
        return (len(reasons) == 0, reasons)

    @property
    def test_suites_by_environment(self):
        test_runs = self.test_runs.prefetch_related(
            'tests',
            'tests__suite',
            'environment',
        )
        template = OrderedDict((
            ('fail', 0),
            ('pass', 0),
            ('skip', 0),
            ('xfail', 0),
        ))
        result = OrderedDict()
        envlist = set([t.environment for t in test_runs])
        for env in sorted(envlist, key=lambda env: env.slug):
            result[env] = dict()
        for tr in test_runs:
            for t in tr.tests.all():
                if t.suite in result[tr.environment].keys():
                    result[tr.environment][t.suite][t.status] += 1
                else:
                    if t.suite not in result[tr.environment]:
                        result[tr.environment][t.suite] = template.copy()
                    result[tr.environment][t.suite][t.status] += 1
        for env in result.keys():
            # there should only be one key in the most nested dict
            result[env] = sorted(
                result[env].items(),
                key=lambda suite_dict: suite_dict[0].slug)

        return result


class BuildPlaceholder(models.Model):
    project = models.ForeignKey(Project, related_name='build_placeholders', on_delete=models.CASCADE)
    version = models.CharField(max_length=100)
    build_deleted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('project', 'version',)


class DelayedReport(models.Model):
    build = models.ForeignKey(Build, related_name="delayed_reports", on_delete=models.CASCADE)
    baseline = models.ForeignKey('ProjectStatus', related_name="delayed_report_baselines", null=True, blank=True, on_delete=models.CASCADE)
    output_format_choices = (('text/plain', 'text/plain'), ('text/html', 'text/html'))
    output_format = models.CharField(max_length=32, choices=output_format_choices)
    template = models.ForeignKey(EmailTemplate, null=True, blank=True, on_delete=models.CASCADE)
    email_recipient = models.EmailField(null=True, blank=True)
    email_recipient_notified = models.BooleanField(default=False)
    callback = models.URLField(null=True, blank=True)
    callback_token = models.CharField(max_length=128, null=True, blank=True)
    callback_notified = models.BooleanField(default=False)
    data_retention_days = models.PositiveSmallIntegerField(default=5, validators=[MaxValueValidator(30)])
    output_subject = models.TextField(null=True, blank=True)
    output_text = models.TextField(null=True, blank=True)
    output_html = models.TextField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True, validators=[yaml_validator])
    status_code = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MaxValueValidator(511), MinValueValidator(100)])
    created_at = models.DateTimeField(auto_now_add=True)

    def send(self):
        recipients = [self.email_recipient]
        if not recipients:
            return

        sender = "%s <%s>" % (settings.SITE_NAME, settings.EMAIL_FROM)
        subject = "Custom report %s" % self.pk

        message = Message(subject, self.output_text, sender, recipients)
        if self.output_html:
            message.attach_alternative(self.output_html, "text/html")
        message.send()
        self.email_recipient_notified = True
        self.save()


class Environment(models.Model):
    project = models.ForeignKey(Project, related_name='environments', on_delete=models.CASCADE)
    slug = models.CharField(max_length=100, validators=[slug_validator], db_index=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    expected_test_runs = models.IntegerField(default=0, null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('project', 'slug',)

    def __str__(self):
        return self.name or self.slug


class TestRunManager(models.Manager):

    __test__ = False

    def get_queryset(self, *args, **kwargs):
        return super(TestRunManager, self).get_queryset(*args, **kwargs).defer(
            "tests_file",
            "metrics_file",
            "log_file",
            "metadata_file",
        )


class TestRun(models.Model):

    __test__ = False

    build = models.ForeignKey(Build, related_name='test_runs', on_delete=models.CASCADE)
    environment = models.ForeignKey(Environment, related_name='test_runs', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    # these fields are potentially very large
    tests_file = models.TextField(null=True)
    metrics_file = models.TextField(null=True)
    log_file = models.TextField(null=True)
    metadata_file = models.TextField(null=True)

    # custom manager to skip potentially large fields by default
    objects = TestRunManager()

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
    test_run = models.ForeignKey(TestRun, related_name='attachments', on_delete=models.CASCADE)
    filename = models.CharField(null=False, max_length=1024)
    data = models.BinaryField(default=None)
    length = models.IntegerField(default=None)


class SuiteMetadata(models.Model):
    suite = models.CharField(max_length=256, db_index=True)
    kind = models.CharField(
        max_length=6,
        choices=(
            ('suite', 'Suite'),
            ('test', 'Test'),
            ('metric', 'Metric'),
        ),
        db_index=True,
    )
    name = models.CharField(max_length=256, null=True, db_index=True)
    description = models.TextField(null=True, blank=True)
    instructions_to_reproduce = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('kind', 'suite', 'name')
        verbose_name_plural = 'Suite metadata'

    def __str__(self):
        if self.name == '-':
            return self.suite
        else:
            return join_name(self.suite, self.name)


class Suite(models.Model):
    project = models.ForeignKey(Project, related_name='suites', on_delete=models.CASCADE)
    slug = models.CharField(max_length=256, validators=[slug_validator], db_index=True)
    name = models.CharField(max_length=256, null=True, blank=True)
    metadata = models.ForeignKey(
        SuiteMetadata,
        null=True,
        related_name='+',
        limit_choices_to={'kind': 'suite'},
        on_delete=models.CASCADE,
    )

    class Meta:
        unique_together = ('project', 'slug',)

    def __str__(self):
        return self.name or self.slug


class SuiteVersion(models.Model):
    suite = models.ForeignKey(Suite, related_name='versions', on_delete=models.CASCADE)
    version = models.CharField(max_length=40, null=True)
    first_seen = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('suite', 'version')

    def __str__(self):
        return '%s %s' % (self.suite.name, self.version)


class Test(models.Model):

    __test__ = False

    test_run = models.ForeignKey(TestRun, related_name='tests', on_delete=models.CASCADE)
    suite = models.ForeignKey(Suite, on_delete=models.CASCADE)
    metadata = models.ForeignKey(
        SuiteMetadata,
        null=True,
        related_name='+',
        limit_choices_to={'kind': 'test'},
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=256, db_index=True)
    result = models.NullBooleanField()
    log = models.TextField(null=True, blank=True)
    known_issues = models.ManyToManyField('KnownIssue')
    has_known_issues = models.NullBooleanField()

    def __str__(self):
        return self.name

    @property
    def status(self):
        if self.result:
            return 'pass'
        elif self.result is None:
            return 'skip'
        else:
            if self.has_known_issues:
                return 'xfail'
            else:
                return 'fail'

    @property
    def full_name(self):
        return join_name(self.suite.slug, self.name)

    @staticmethod
    def prefetch_related(tests):
        prefetch_related_objects(
            tests,
            'known_issues',
            'test_run',
            'test_run__environment',
            'test_run__build',
            'test_run__build__project',
            'test_run__build__project__group',
            'test_run__status',
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
    test_run = models.ForeignKey(TestRun, related_name='metrics', on_delete=models.CASCADE)
    suite = models.ForeignKey(Suite, on_delete=models.CASCADE)
    metadata = models.ForeignKey(
        SuiteMetadata,
        null=True,
        related_name='+',
        limit_choices_to={'kind': 'metric'},
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=100)
    result = models.FloatField()
    measurements = models.TextField()  # comma-separated float numbers
    is_outlier = models.BooleanField(default=False)

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

    __test__ = False

    @property
    def tests_total(self):
        return self.tests_pass + self.tests_fail + self.tests_xfail + self.tests_skip

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
        return self.__percent__(self.tests_fail + self.tests_xfail)

    @property
    def skip_percentage(self):
        return self.__percent__(self.tests_skip)

    @property
    def has_tests(self):
        return self.tests_total > 0


class Status(models.Model, TestSummaryBase):
    test_run = models.ForeignKey(TestRun, related_name='status', on_delete=models.CASCADE)
    suite = models.ForeignKey(Suite, null=True, on_delete=models.CASCADE)
    suite_version = models.ForeignKey(SuiteVersion, null=True, on_delete=models.CASCADE)

    tests_pass = models.IntegerField(default=0)
    tests_fail = models.IntegerField(default=0)
    tests_xfail = models.IntegerField(default=0)
    tests_skip = models.IntegerField(default=0)
    metrics_summary = models.FloatField(default=0.0)
    has_metrics = models.BooleanField(default=False)

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

    def __str__(self):
        if self.suite:
            name = self.suite.slug + ' on ' + self.environment.slug
        else:
            name = self.environment.slug
        return '%s: %f, %d%% pass' % (name, self.metrics_summary, self.pass_percentage)


class MetricThreshold(models.Model):

    class Meta:
        unique_together = ('environment', 'name',)

    environment = models.ForeignKey(Environment, null=False, on_delete=models.CASCADE)
    name = models.CharField(max_length=1024)
    value = models.FloatField()
    is_higher_better = models.BooleanField(default=False)


class ProjectStatus(models.Model, TestSummaryBase):
    """
    Represents a "checkpoint" of a project status in time. It is used by the
    notification system to know what was the project status at the time of the
    last notification.
    """
    build = models.OneToOneField('Build', related_name='status', on_delete=models.CASCADE)
    baseline = models.ForeignKey('Build', related_name='next_statuses', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(null=True)
    finished = models.BooleanField(default=False)
    notified = models.BooleanField(default=False)
    notified_on_timeout = models.NullBooleanField(default=None)
    approved = models.BooleanField(default=False)

    metrics_summary = models.FloatField(null=True)
    has_metrics = models.BooleanField(default=False)

    tests_pass = models.IntegerField(default=0)
    tests_fail = models.IntegerField(default=0)
    tests_xfail = models.IntegerField(default=0)
    tests_skip = models.IntegerField(default=0)

    test_runs_total = models.IntegerField(default=0)
    test_runs_completed = models.IntegerField(default=0)
    test_runs_incomplete = models.IntegerField(default=0)

    regressions = models.TextField(
        null=True,
        blank=True,
        validators=[yaml_validator]
    )
    fixes = models.TextField(
        null=True,
        blank=True,
        validators=[yaml_validator]
    )

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
        test_runs_total = build.test_runs.count()
        test_runs_completed = build.test_runs.filter(completed=True).count()
        test_runs_incomplete = build.test_runs.filter(completed=False).count()
        regressions = None
        fixes = None

        previous_build = None
        if build.status is not None and build.status.baseline is not None:
            previous_build = build.status.baseline
        else:
            previous_build = Build.objects.filter(
                status__finished=True,
                datetime__lt=build.datetime,
                project=build.project,
            ).order_by('datetime').last()
        if previous_build is not None:
            comparison = TestComparison(previous_build, build)
            if comparison.regressions:
                regressions = yaml.dump(comparison.regressions)
            if comparison.fixes:
                fixes = yaml.dump(comparison.fixes)

        finished, _ = build.finished
        data = {
            'tests_pass': test_summary.tests_pass,
            'tests_fail': test_summary.tests_fail,
            'tests_xfail': test_summary.tests_xfail,
            'tests_skip': test_summary.tests_skip,
            'metrics_summary': metrics_summary.value,
            'has_metrics': metrics_summary.has_metrics,
            'last_updated': now,
            'finished': finished,
            'test_runs_total': test_runs_total,
            'test_runs_completed': test_runs_completed,
            'test_runs_incomplete': test_runs_incomplete,
            'regressions': regressions,
            'fixes': fixes,
            'baseline': previous_build,
        }

        status, created = cls.objects.get_or_create(
            build=build,
            defaults=data)
        if not created and test_summary.tests_total >= status.tests_total:
            # XXX the test above for the new total number of tests prevents
            # results that arrived earlier, but are only being processed now,
            # from overwriting a ProjectStatus created by results that arrived
            # later but were already processed.
            status.tests_pass = test_summary.tests_pass
            status.tests_fail = test_summary.tests_fail
            status.tests_xfail = test_summary.tests_xfail
            status.tests_skip = test_summary.tests_skip
            status.metrics_summary = metrics_summary.value
            status.has_metrics = metrics_summary.has_metrics
            status.last_updated = now
            status.finished = finished
            status.build = build
            status.baseline = previous_build
            status.test_runs_total = test_runs_total
            status.test_runs_completed = test_runs_completed
            status.test_runs_incomplete = test_runs_incomplete
            status.regressions = regressions
            status.fixes = fixes
            status.save()
        return status

    def __str__(self):
        return "%s, build %s" % (self.build.project, self.build.version)

    def get_previous(self):
        if self.baseline is None:
            previous_status = ProjectStatus.objects.filter(
                finished=True,
                build__datetime__lt=self.build.datetime,
                build__project=self.build.project,
            ).order_by('build__datetime').last()
            if previous_status is not None:
                self.baseline = previous_status.build
                self.save()
        if hasattr(self.baseline, 'status'):
            return self.baseline.status
        return None

    def __get_yaml_field__(self, field_value):
        if field_value is not None:
            return yaml.load(field_value, Loader=yaml.Loader)
        return {}

    def get_regressions(self):
        return self.__get_yaml_field__(self.regressions)

    def get_fixes(self):
        return self.__get_yaml_field__(self.fixes)

    def get_exceeded_thresholds(self):
        # Return a list of all (threshold, metric) objects for those
        # thresholds that were exceeded by corresponding metrics.
        thresholds_exceeded = []
        fullname = Concat(F('suite__slug'), Value('/'), F('name'))
        if self.has_metrics:
            test_runs = self.build.test_runs.all()
            suites = Suite.objects.filter(test__test_run__build=self.build)
            thresholds = MetricThreshold.objects.filter(
                environment__in=self.build.project.environments.all())
            thresholds_names = thresholds.values_list('name', flat=True)
            for metric in Metric.objects.annotate(fullname=fullname).filter(
                    Q(test_run__in=test_runs) | Q(suite__in=suites),
                    fullname__in=thresholds_names):
                for threshold in thresholds:
                    if metric.test_run.environment_id != threshold.environment_id:
                        continue
                    if threshold.is_higher_better:
                        if metric.result < threshold.value:
                            thresholds_exceeded.append((threshold, metric))
                    else:
                        if metric.result > threshold.value:
                            thresholds_exceeded.append((threshold, metric))
        return thresholds_exceeded


class NotificationDelivery(models.Model):

    status = models.ForeignKey('ProjectStatus', related_name='deliveries', on_delete=models.CASCADE)
    subject = models.CharField(max_length=40, null=True, blank=True)
    txt = models.CharField(max_length=40, null=True, blank=True)
    html = models.CharField(max_length=40, null=True, blank=True)

    class Meta:
        unique_together = ('status', 'subject', 'txt', 'html')

    @classmethod
    def exists(cls, status, subject, txt, html):
        subject_hash = sha1(subject.encode()).hexdigest()
        txt_hash = sha1(txt.encode()).hexdigest()
        html_hash = sha1(html.encode()).hexdigest()
        obj, created = cls.objects.get_or_create(
            status=status,
            subject=subject_hash,
            txt=txt_hash,
            html=html_hash,
        )
        return (not created)


class TestSummary(TestSummaryBase):

    __test__ = False

    def __init__(self, build, environment=None):
        self.tests_pass = 0
        self.tests_fail = 0
        self.tests_xfail = 0
        self.tests_skip = 0

        query_set = build.test_runs
        if environment:
            query_set = query_set.filter(environment=environment)

        query_set = query_set.values('id').order_by('id')

        test_runs_ids = [test_run['id'] for test_run in query_set]
        for chunk in split_list(test_runs_ids, chunk_size=100):
            status = Status.objects.filter(suite=None, test_run_id__in=chunk)
            for s in status:
                self.tests_pass += s.tests_pass
                self.tests_fail += s.tests_fail
                self.tests_xfail += s.tests_xfail
                self.tests_skip += s.tests_skip


class MetricsSummary(object):

    def __init__(self, build, environment=None):
        queryset = Metric.objects.filter(test_run__build_id=build.id)
        if environment:
            queryset = queryset.filter(test_run__environment_id=environment.id)
        metrics = queryset.all()
        values = [m.result for m in metrics]
        self.value = geomean(values)
        self.has_metrics = len(values) > 0


class BuildSummary(models.Model, TestSummaryBase):
    build = models.ForeignKey(Build, related_name='metrics_summary', on_delete=models.CASCADE)
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE)
    metrics_summary = models.FloatField(null=True)
    has_metrics = models.BooleanField(default=False)

    tests_pass = models.IntegerField(default=0)
    tests_fail = models.IntegerField(default=0)
    tests_xfail = models.IntegerField(default=0)
    tests_skip = models.IntegerField(default=0)
    test_runs_total = models.IntegerField(default=0)
    test_runs_completed = models.IntegerField(default=0)
    test_runs_incomplete = models.IntegerField(default=0)

    @classmethod
    def create_or_update(cls, build, environment):
        """
        Creates (or updates) a BuildSummary given build/environment and
        returns it.
        """

        metrics_summary = MetricsSummary(build, environment)
        test_summary = TestSummary(build, environment)
        test_runs_total = build.test_runs.filter(environment=environment).count()
        test_runs_completed = build.test_runs.filter(environment=environment, completed=True).count()
        test_runs_incomplete = build.test_runs.filter(environment=environment, completed=False).count()

        data = {
            'metrics_summary': metrics_summary.value,
            'has_metrics': metrics_summary.has_metrics,
            'tests_pass': test_summary.tests_pass,
            'tests_fail': test_summary.tests_fail,
            'tests_xfail': test_summary.tests_xfail,
            'tests_skip': test_summary.tests_skip,
            'test_runs_total': test_runs_total,
            'test_runs_completed': test_runs_completed,
            'test_runs_incomplete': test_runs_incomplete,
        }

        summary, created = cls.objects.get_or_create(build=build, environment=environment, defaults=data)
        if not created:
            summary.metrics_summary = metrics_summary.value
            summary.has_metrics = metrics_summary.has_metrics
            summary.tests_pass = test_summary.tests_pass
            summary.tests_fail = test_summary.tests_fail
            summary.tests_xfail = test_summary.tests_xfail
            summary.tests_skip = test_summary.tests_skip
            summary.test_runs_total = test_runs_total
            summary.test_runs_completed = test_runs_completed
            summary.test_runs_incomplete = test_runs_incomplete
            summary.save()
        return summary


class Subscription(models.Model):
    project = models.ForeignKey(Project, related_name='subscriptions', on_delete=models.CASCADE)
    email = models.CharField(
        max_length=1024,
        null=True,
        blank=True,
        validators=[EmailValidator()]
    )
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        default=None,
        on_delete=models.CASCADE,
    )

    NOTIFY_ALL_BUILDS = 'all'
    NOTIFY_ON_CHANGE = 'change'
    NOTIFY_ON_REGRESSION = 'regression'

    STRATEGY_CHOICES = (
        (NOTIFY_ALL_BUILDS, N_("All builds")),
        (NOTIFY_ON_CHANGE, N_("Only on change")),
        (NOTIFY_ON_REGRESSION, N_("Only on regression")),
    )

    notification_strategy = models.CharField(
        max_length=32,
        choices=STRATEGY_CHOICES,
        default='all'
    )

    class Meta:
        unique_together = ('project', 'user',)

    def _validate_email(self):
        if (not self.email) == (not self.user):
            raise ValidationError("Subscription object must have exactly one of 'user' and 'email' fields populated.")

    def save(self, *args, **kwargs):
        self._validate_email()
        super().save(*args, **kwargs)

    def clean(self):
        self._validate_email()

    def get_email(self):
        if self.user and self.user.email:
            return self.user.email
        return self.email

    def __str__(self):
        return '%s on %s' % (self.get_email(), self.project)


class AdminSubscription(models.Model):
    project = models.ForeignKey(Project, related_name='admin_subscriptions', on_delete=models.CASCADE)
    email = models.CharField(max_length=1024, validators=[EmailValidator()])

    def __str__(self):
        return '%s on %s' % (self.email, self.project)


class KnownIssue(models.Model):
    title = models.CharField(max_length=1024)
    test_name = models.CharField(max_length=1024)

    url = models.URLField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    active = models.BooleanField(default=True)
    intermittent = models.BooleanField(default=False)
    environments = models.ManyToManyField(Environment)

    @classmethod
    def active_by_environment(cls, environment):
        return cls.objects.filter(active=True, environments=environment)

    @classmethod
    def active_by_project_and_test(cls, project, test_name=None):
        qs = cls.objects.filter(active=True, environments__project=project).prefetch_related('environments')
        if test_name:
            qs = qs.filter(test_name=test_name)
        return qs.distinct()


class Annotation(models.Model):
    description = models.CharField(max_length=1024, null=True, blank=True)
    build = models.OneToOneField(Build, on_delete=models.CASCADE)

    def __str__(self):
        return '%s' % self.description
