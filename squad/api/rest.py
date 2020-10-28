import json
import yaml

from django.db.models import Q, F, Value as V, CharField, Prefetch
from django.db.models.functions import Concat
from django.core import exceptions as core_exceptions
from django.core.validators import validate_email
from django.contrib.auth.models import User
from squad.core.models import (
    Annotation,
    Group,
    Project,
    ProjectStatus,
    Build,
    TestRun,
    Environment,
    Test,
    Metric,
    MetricThreshold,
    EmailTemplate,
    KnownIssue,
    PatchSource,
    Suite,
    SuiteMetadata,
    DelayedReport,
    Subscription,
    Status
)
from squad.core.tasks import prepare_report, update_delayed_report
from squad.core.comparison import TestComparison
from squad.core.utils import parse_name, log_addition, log_change, log_deletion
from squad.ci.models import Backend, TestJob
from squad.compat import drf_basename
from django.http import HttpResponse
from django.urls import reverse
from django import forms
from django.utils.translation import ugettext as _
from rest_framework_extensions.routers import ExtendedDefaultRouter
from rest_framework_extensions.mixins import NestedViewSetMixin
from rest_framework import routers, serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.reverse import reverse as rest_reverse
from rest_framework.permissions import AllowAny
from squad.compat import ComplexFilterBackend
from squad.api.utils import CursorPaginationWithPageSize

import rest_framework_filters as filters

import logging


logger = logging.getLogger()


class GroupFilter(filters.FilterSet):
    class Meta:
        model = Group
        fields = {'name': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  'slug': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  'id': ['exact', 'in']}


class ProjectFilter(filters.FilterSet):
    group = filters.RelatedFilter(GroupFilter, field_name="group", queryset=Group.objects.all())
    full_name = filters.CharFilter(method='filter_full_name', lookup_expr='icontains')

    class Meta:
        model = Project
        fields = {'name': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  'slug': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  'id': ['exact', 'in']}

    def filter_full_name(self, queryset, field_name, value):
        if value:
            group_slug = 'group__slug'
            project_slug = 'slug'
            if queryset.model is not Project:
                group_slug = 'project__%s' % group_slug
                project_slug = 'project__%s' % project_slug
            queryset = queryset.annotate(fullname=Concat(F(group_slug), V('/'), F(project_slug),
                                         output_field=CharField())).filter(fullname__startswith=value)
        return queryset


class EnvironmentFilter(filters.FilterSet):
    project = filters.RelatedFilter(ProjectFilter, field_name="project", queryset=Project.objects.all(), widget=forms.TextInput)

    class Meta:
        model = Environment
        fields = {'name': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  'slug': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  'id': ['exact', 'in']}


class ProjectStatusFilter(filters.FilterSet):

    class Meta:
        model = ProjectStatus
        fields = {'finished': ['exact', 'in'],
                  'approved': ['exact', 'in'],
                  'notified': ['exact', 'in'],
                  'has_metrics': ['exact', 'in'],
                  'last_updated': ['gt', 'lt']}


class BuildFilter(filters.FilterSet):
    project = filters.RelatedFilter(ProjectFilter, field_name="project", queryset=Project.objects.all(), widget=forms.TextInput)
    status = filters.RelatedFilter(ProjectStatusFilter, field_name="status", queryset=ProjectStatus.objects.all(), widget=forms.TextInput)

    class Meta:
        model = Build
        fields = {'version': ['exact', 'in', 'startswith'],
                  'id': ['exact', 'in'],
                  'created_at': ['exact', 'lt', 'lte', 'gt', 'gte'],
                  }


def unordered_build_queryset(request):
    queryset = Build.objects.all()
    queryset.query.clear_ordering(True)
    return queryset


class TestRunFilter(filters.FilterSet):
    build = filters.RelatedFilter(BuildFilter, field_name="build", queryset=unordered_build_queryset, widget=forms.TextInput)
    environment = filters.RelatedFilter(EnvironmentFilter, field_name="environment", queryset=Environment.objects.all(), widget=forms.TextInput)

    class Meta:
        model = TestRun
        fields = {'id': ['exact', 'in'],
                  'job_id': ['exact', 'in', 'startswith'],
                  'job_status': ['exact', 'in', 'startswith'],
                  'data_processed': ['exact'],
                  'status_recorded': ['exact'],
                  'completed': ['exact']}


class TestJobFilter(filters.FilterSet):
    testrun = filters.RelatedFilter(TestRunFilter, field_name="testrun", queryset=TestRun.objects.all(), widget=forms.TextInput)
    target_build = filters.RelatedFilter(BuildFilter, field_name="target_build", queryset=Build.objects.all(), widget=forms.TextInput)
    target = filters.RelatedFilter(ProjectFilter, field_name="target", queryset=Project.objects.all(), widget=forms.TextInput)

    class Meta:
        model = TestJob
        fields = {'name': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  "environment": ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  "submitted": ['exact', 'in'],
                  "fetched": ['exact', 'in'],
                  "fetch_attempts": ['exact', 'in'],
                  "last_fetch_attempt": ['exact', 'in', 'lt', 'gt', 'lte', 'gte'],
                  "failure": ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  "can_resubmit": ['exact', 'in'],
                  "resubmitted_count": ['exact', 'in'],
                  "job_status": ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  "job_id": ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  "id": ['exact', 'in']}


class SuiteFilter(filters.FilterSet):
    project = filters.RelatedFilter(ProjectFilter, field_name="project", queryset=Project.objects.all(), widget=forms.TextInput)

    class Meta:
        model = Suite
        fields = {'id': ['exact', 'in'],
                  'name': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  'slug': ['exact', 'in', 'startswith', 'contains', 'icontains']}


class SuiteMetadataFilter(filters.FilterSet):

    class Meta:
        model = SuiteMetadata
        fields = {'id': ['exact', 'in'],
                  'name': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  'suite': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  'kind': ['exact', 'in', 'startswith', 'contains', 'icontains']}


class KnownIssueFilter(filters.FilterSet):
    environment = filters.RelatedFilter(EnvironmentFilter, field_name="environments", queryset=Environment.objects.all(), widget=forms.TextInput)

    class Meta:
        model = KnownIssue
        fields = {'title': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  'test_name': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  'url': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  'active': ['exact', 'in'],
                  'intermittent': ['exact', 'in'],
                  'id': ['exact', 'in']}


class TestFilter(filters.FilterSet):
    test_run = filters.RelatedFilter(TestRunFilter, field_name="test_run", queryset=TestRun.objects.all(), widget=forms.TextInput)
    suite = filters.RelatedFilter(SuiteFilter, field_name="suite", queryset=Suite.objects.all(), widget=forms.TextInput)
    known_issues = filters.RelatedFilter(KnownIssueFilter, field_name='known_issues', queryset=KnownIssue.objects.all(), widget=forms.TextInput)
    name = filters.CharFilter(lookup_expr='icontains', field_name='metadata__name')

    class Meta:
        model = Test
        fields = {'result': ['exact', 'in'],
                  'has_known_issues': ['exact', 'in']}


class MetricFilter(filters.FilterSet):
    test_run = filters.RelatedFilter(TestRunFilter, field_name="test_run", queryset=TestRun.objects.all(), widget=forms.TextInput)
    suite = filters.RelatedFilter(SuiteFilter, field_name="suite", queryset=Suite.objects.all(), widget=forms.TextInput)

    class Meta:
        model = Metric
        fields = {'name': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  'result': ['exact', 'in'],
                  'test_run': ['exact', 'in'],
                  'is_outlier': ['exact', 'in'],
                  'suite': ['exact', 'in'],
                  'unit': ['exact', 'in']}


class MetricThresholdFilter(filters.FilterSet):
    environment = filters.RelatedFilter(EnvironmentFilter,
                                        field_name="environment",
                                        queryset=Environment.objects.all(),
                                        widget=forms.TextInput)

    class Meta:
        model = MetricThreshold
        fields = {'name': ['exact', 'in', 'startswith', 'contains', 'icontains'],
                  'id': ['exact', 'in']}


class DelayedReportFilter(filters.FilterSet):
    build = filters.RelatedFilter(BuildFilter, field_name="build", queryset=Build.objects.all(), widget=forms.TextInput)
    baseline = filters.RelatedFilter(BuildFilter, field_name="baseline", queryset=Build.objects.all(), widget=forms.TextInput)

    class Meta:
        model = DelayedReport
        fields = {
            "output_format": ['exact', 'in', 'startswith', 'contains', 'icontains'],
            "id": ['exact', 'in'],
            "template": ['exact', 'in'],
            "email_recipient": ['exact', 'in', 'startswith', 'contains', 'icontains'],
            "email_recipient_notified": ['exact'],
            "callback": ['exact', 'in', 'startswith', 'contains', 'icontains'],
            "callback_notified": ['exact'],
            "data_retention_days": ['exact', 'in'],
            "output_text": ['exact', 'in', 'startswith', 'contains', 'icontains'],
            "output_html": ['exact', 'in', 'startswith', 'contains', 'icontains'],
            "error_message": ['exact', 'in', 'startswith', 'contains', 'icontains'],
            "status_code": ['exact', 'in'],
            "created_at": ['exact', 'gt', 'lt'],
        }


class API(routers.APIRootView):
    """
    Welcome to the SQUAD API. This API is self-describing, i.e. all of the
    available endpoints are accessible from this browseable user interface, and
    are self-describing themselves. See below for a list of them.

    Notes on the API:

    * All requests for lists of objects are paginated by default. Make sure you
      take the `count` and `next` fields of the response into account so you can
      navigate to the rest of the objects.

    * Only public projects are available through the API without
      authentication. Non-public projects require authentication using a valid
      API token, and the corresponding user account must also have access to
      the project in question.

    * All URLs displayed in this API browser are clickable.

    * Client interaction is enabled with <a href="/api/schema/">/api/schema</a>
    URL.

    * Testrun statuses are available at:
        * `/testruns/<testrun_id>/status/`
    """

    def get_view_name(self):
        return "API"


class APIRouter(ExtendedDefaultRouter):

    APIRootView = API


class ModelViewSet(viewsets.ModelViewSet):
    project_lookup_key = None

    def get_projects(self):
        """
        Determines which projects the current user is allowed to visualize.
        Returns a list of project ids to be used in get_queryset() for
        filtering.
        """
        user = self.request.user
        return Project.objects.accessible_to(user).only('id')

    def get_queryset(self):
        queryset = self.queryset
        user = self.request.user
        if not (user.is_superuser or user.is_staff) and self.project_lookup_key is not None:
            project_lookup = {self.project_lookup_key: self.get_projects()}
            queryset = queryset.filter(**project_lookup)

        return queryset


class GroupSerializer(serializers.HyperlinkedModelSerializer):

    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Group
        exclude = ('members',)


class GroupViewSet(viewsets.ModelViewSet):
    """
    List of groups. Includes public groups and groups that the current
    user has access to.
    """
    queryset = Group.objects
    serializer_class = GroupSerializer
    filterset_fields = ('slug', 'name')
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore
    filterset_class = GroupFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore
    filter_backends = (ComplexFilterBackend, )
    search_fields = ('slug', 'name')
    ordering_fields = ('slug', 'name')

    def get_queryset(self):
        return self.queryset.accessible_to(self.request.user)


class ProjectSerializer(serializers.HyperlinkedModelSerializer):

    builds = serializers.HyperlinkedIdentityField(
        view_name='project-builds',
    )
    id = serializers.IntegerField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    enabled_plugins_list = serializers.ListField(
        child=serializers.CharField()
    )

    class Meta:
        model = Project
        fields = '__all__'


class LatestTestResultsSerializer(serializers.BaseSerializer):
    def to_representation(self, build):
        metadata = self.context.get('metadata')
        project_environments = self.context.get('environments')
        suite = self.context.get('suite')

        test_runs = {tr.id: tr.environment for tr in build.test_runs.all()}
        tests = Test.objects.filter(
            test_run_id__in=test_runs.keys(),
            metadata=metadata,
        ).prefetch_related('metadata').order_by()

        environments = {
            e: {
                'test': TestSerializer(None, context=self.context).data,
                'environment': EnvironmentSerializer(e, context=self.context).data
            }
            for e in project_environments
        }
        for test in tests.all():
            e = test_runs[test.test_run_id]
            test.suite = suite
            environments[e]['test'] = TestSerializer(test, context=self.context, remove_fields=['known_issues']).data
            environments[e]['test_url_path'] = reverse('test_history', args=[
                build.project.group.slug,
                build.project.slug,
                build.version,
                test.test_run_id,
                metadata.suite.replace('/', '$'),
                metadata.name
            ])

        serialized_obj = {
            'build': BuildSerializer(build, context=self.context).data,
            'build_url_path': reverse(
                'build',
                args=[
                    build.project.group.slug,
                    build.project.slug,
                    build.version
                ]),
            'environments': environments.values()
        }
        return serialized_obj


class SuiteMetadataSerializer(serializers.HyperlinkedModelSerializer):

    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = SuiteMetadata
        fields = '__all__'


class SuiteMetadataViewset(viewsets.ModelViewSet):
    queryset = SuiteMetadata.objects
    serializer_class = SuiteMetadataSerializer
    filterset_fields = ('suite', 'kind', 'name')
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore
    filterset_class = SuiteMetadataFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore
    ordering_fields = ('name', 'suite')

    def get_queryset(self):
        request = self.request
        suites_qs = self.queryset
        project_ids = request.query_params.get("project", None)
        project_qs = Project.objects.all()
        try:
            if project_ids:
                projects = project_ids.split(",")
                project_qs = project_qs.filter(id__in=projects)
                suites_names = Suite.objects.filter(project__in=project_qs).values_list('slug')
                suites_qs = suites_qs.filter(suite__in=suites_names)
        except ValueError as e:
            logger.warning(e)

        return suites_qs


class ProjectViewSet(viewsets.ModelViewSet):
    """
    List of projects. Includes public projects and projects that the current
    user has access to.

    Additional actions:

     * `api/projects/<id>/builds` GET

        List of builds for the current project.

     * `api/projects/<id>/suites` GET

        List of test suite names available in this project

     * `api/projects/<id>/tests` GET

        List of test names available in this project

     * `api/projects/<id>/test_results` GET

        Test results of the last build

     * `api/projects/<id>/subscribe` POST

        Subscribe to project notifications

     * `api/projects/<id>/unsubscribe` POST

        Unsubscribe from project notifications

    * `api/projects/<id>/compare_builds` POST/GET

        Compares two builds and report regressions/fixes
    """
    queryset = Project.objects
    serializer_class = ProjectSerializer
    filterset_fields = (
        'group',
        'slug',
        'name',
        'is_public',
        'html_mail',
        'custom_email_template',
        'moderate_notifications',
    )
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore
    filter_backends = (ComplexFilterBackend, )
    filterset_class = ProjectFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore
    search_fields = ('slug',
                     'name',)
    ordering_fields = ('slug',
                       'name',)

    def get_queryset(self):
        return self.queryset.accessible_to(self.request.user)

    @action(detail=True, methods=['get'], suffix='builds')
    def builds(self, request, pk=None):
        """
        List of builds for the current project.
        """
        builds = self.get_object().builds.prefetch_related('test_runs').order_by('-datetime')
        page = self.paginate_queryset(builds)
        serializer = BuildSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['get'], suffix='suites')
    def suites(self, request, pk=None):
        """
        List of test suite names available in this project
        """
        suites_names = self.get_object().suites.values_list('slug')
        suites_metadata = SuiteMetadata.objects.filter(kind='suite', suite__in=suites_names)
        page = self.paginate_queryset(suites_metadata)
        serializer = SuiteMetadataSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['get'], suffix='tests')
    def tests(self, request, pk=None):
        """
        List of test names available in this project
        """
        suite_name = request.query_params.get("suite_name", None)
        if suite_name is None:
            suites_names = self.get_object().suites.values_list('slug')
        else:
            suites_names = [suite_name]
        suites_metadata = SuiteMetadata.objects.filter(kind='test', suite__in=suites_names)
        page = self.paginate_queryset(suites_metadata)
        serializer = SuiteMetadataSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['get'], suffix='test_results')
    def test_results(self, request, pk=None):
        test_full_name = request.query_params.get('test_name', None)
        if test_full_name is None:
            raise serializers.ValidationError(_('"test_name" parameter is mandatory. Ex: suitename/testname'))

        suite_slug, test_name = parse_name(test_full_name)
        try:
            metadata = SuiteMetadata.objects.get(kind='test', suite=suite_slug, name=test_name)
        except SuiteMetadata.DoesNotExist:
            raise serializers.ValidationError(_('There is no test named "%s/%s"' % (suite_slug, test_name)))

        project = self.get_object()
        builds = project.builds.prefetch_related('test_runs__environment', 'project__group', 'status').order_by('-datetime')
        environments = project.environments.order_by('name', 'slug')

        try:
            suite = project.suites.get(slug=suite_slug)
        except Suite.DoesNotExist:
            return Response()

        page = self.paginate_queryset(builds)
        serializer = LatestTestResultsSerializer(
            page,
            many=True,
            context={'request': request, 'suite': suite, 'metadata': metadata, 'environments': environments}
        )
        return Response(serializer.data)

    @action(detail=True, methods=['post'], suffix='subscribe')
    def subscribe(self, request, pk=None):
        subscriber_email = request.data.get("email", None)
        if subscriber_email is None:
            raise serializers.ValidationError("'email' field is mandatory.")
        try:
            validate_email(subscriber_email)
        except core_exceptions.ValidationError:
            raise serializers.ValidationError("Invalid 'email' field value.")
        user = User.objects.filter(email=subscriber_email).first()
        if user is None:
            sub, created = Subscription.objects.get_or_create(email=subscriber_email, project=self.get_object())
            if created:
                log_addition(request, sub, "Subscription created")
        else:
            sub, created = Subscription.objects.get_or_create(user=user, project=self.get_object())
            if created:
                log_addition(request, sub, "Subscription created")
        data = {"email": subscriber_email}
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], suffix='unsubscribe')
    def unsubscribe(self, request, pk=None):
        subscriber_email = request.data.get("email", None)
        if subscriber_email is None:
            raise serializers.ValidationError("'email' field is mandatory.")
        try:
            validate_email(subscriber_email)
        except core_exceptions.ValidationError:
            raise serializers.ValidationError("Invalid 'email' field value.")
        subs = self.get_object().subscriptions.filter(Q(email=subscriber_email) | Q(user__email=subscriber_email))
        for sub in subs:
            log_deletion(request, sub, "Subscription deleted")
        subs.delete()
        data = {"email": subscriber_email}
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get', 'post'], suffix='compare_builds')
    def compare_builds(self, request, pk=None):
        builds_to_compare = {f: request.GET.get(f, request.POST.get(f, None)) for f in ['baseline', 'to_compare']}
        if all(builds_to_compare.values()):
            try:
                int(builds_to_compare['baseline'])
                int(builds_to_compare['to_compare'])
                baseline = self.get_object().builds.get(pk=builds_to_compare['baseline'])
                to_compare = self.get_object().builds.get(pk=builds_to_compare['to_compare'])
                if not baseline.status.finished or not to_compare.status.finished:
                    raise serializers.ValidationError("Cannot report regressions/fixes on a non-finished builds")
            except Build.DoesNotExist:
                raise NotFound()
            except ValueError:
                raise serializers.ValidationError("builds IDs must be integer")
        else:
            raise serializers.ValidationError("Invalid args provided. 'baseline' and 'to_compare' build ids must NOT be empty")

        if baseline and to_compare:
            comparison = TestComparison(baseline, to_compare)
            serializer = BuildsComparisonSerializer(comparison)
            return Response(serializer.data)


class ProjectStatusSerializer(serializers.HyperlinkedModelSerializer):

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        enriched_details = self.context.get('enriched_details', None)
        if instance.regressions is not None:
            regressions = instance.get_regressions()
            if enriched_details:
                for env in enriched_details.keys():
                    env_regressions = regressions.get(env, None)
                    if env_regressions:
                        enriched_details[env].update({'regressions': env_regressions})
            ret['regressions'] = json.dumps(regressions)
        if instance.fixes is not None:
            fixes = instance.get_fixes()
            if enriched_details:
                for env in enriched_details.keys():
                    print(env)
                    env_fixes = fixes.get(env, None)
                    if env_fixes:
                        enriched_details[env].update({'fixes': env_fixes})
            ret['fixes'] = json.dumps(instance.get_fixes())
        ret['details'] = enriched_details
        return ret

    class Meta:
        model = ProjectStatus
        fields = ('last_updated',
                  'finished',
                  'notified',
                  'notified_on_timeout',
                  'approved',
                  'tests_pass',
                  'tests_fail',
                  'tests_skip',
                  'tests_xfail',
                  'tests_total',
                  'pass_percentage',
                  'fail_percentage',
                  'skip_percentage',
                  'test_runs_total',
                  'test_runs_completed',
                  'test_runs_incomplete',
                  'has_metrics',
                  'has_tests',
                  'metrics_summary',
                  'build',
                  'baseline',
                  'created_at',
                  'regressions',
                  'fixes')


class ProjectStatusViewSet(viewsets.ModelViewSet):
    queryset = ProjectStatus.objects
    serializer_class = ProjectStatusSerializer
    filterset_fields = ('build',)
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore
    filterset_class = ProjectStatusFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore

    ordering_fields = ('created_at', 'last_updated')


class PatchSourceSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = PatchSource
        fields = '__all__'
        extra_kwargs = {
            'token': {'write_only': True},
            'username': {'write_only': True},
            '_password': {'write_only': True},
        }


class PatchSourceViewSet(viewsets.ModelViewSet):
    queryset = PatchSource.objects
    serializer_class = PatchSourceSerializer
    filterset_fields = ('implementation', 'url', 'name')
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore


class HyperlinkedProjectStatusField(serializers.HyperlinkedRelatedField):
    def get_url(self, obj, view_name, request, format):
        try:
            project_status = ProjectStatus.objects.get(pk=obj.pk)
            return rest_reverse(view_name, kwargs={'pk': project_status.build.pk}, request=request, format=format)
        except ProjectStatus.DoesNotExist:
            return None


class DelayedReportSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True)
    baseline = HyperlinkedProjectStatusField(
        view_name='build-status',
        read_only=True,
        many=False)

    class Meta:
        model = DelayedReport
        exclude = ('callback_token',)


class DelayedReportViewSet(viewsets.ReadOnlyModelViewSet):

    queryset = DelayedReport.objects
    serializer_class = DelayedReportSerializer
    filterset_fields = ('build', 'baseline', 'callback', 'callback_notified', 'email_recipient', 'status_code', 'error_message', 'created_at')
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore
    filterset_class = DelayedReportFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore
    ordering_fields = ('id', 'created_at')


class BuildsComparisonSerializer(serializers.BaseSerializer):
    def to_representation(self, comparison):
        ret = {}
        if comparison.regressions is not None:
            ret['regressions'] = comparison.regressions_grouped_by_suite
        if comparison.fixes is not None:
            ret['fixes'] = comparison.fixes_grouped_by_suite
        return ret


class BuildSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True)
    testruns = serializers.HyperlinkedIdentityField(view_name='build-testruns')
    testjobs = serializers.HyperlinkedIdentityField(view_name='build-testjobs')
    status = serializers.HyperlinkedIdentityField(read_only=True, view_name='build-status', allow_null=True)
    metadata = serializers.HyperlinkedIdentityField(read_only=True, view_name='build-metadata')
    finished = serializers.BooleanField(read_only=True, source='status.finished')

    class Meta:
        model = Build
        fields = '__all__'


class BuildViewSet(ModelViewSet):
    """
    List of all builds in the system. Only builds belonging to public projects
    and to projects you have access to are available.

    Additional actions:

     * `api/builds/<id>/metadata` GET

        Build metadata list

     * `api/builds/<id>/status` GET

        Build status and cached test/metric totals

     * `api/builds/<id>/testruns` GET

        List of test runs in the build

     * `api/builds/<id>/testjobs` GET

        List of test jobs in the build (if any)

     * `api/builds/<id>/email` GET

        This method produces the body of email notification for the build.
        By default it uses the project settings for HTML and template.
        These settings can be overwritten by using GET parameters:

         * output - sets the output format (text/plan, text/html)
         * template - sets the template used (id of existing template or
                      "default" for default SQUAD templates)
         * force - force email report re-generation even if there is
                   existing one cached

     * `api/builds/<id>/report` GET, POST

        Similar to 'email' but asunchronous
    """
    queryset = Build.objects.prefetch_related('status', 'test_runs').order_by('-datetime').all()
    project_lookup_key = 'project__in'
    serializer_class = BuildSerializer
    filterset_fields = ('version', 'project')
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore
    filterset_class = BuildFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore
    search_fields = ('version',)
    ordering_fields = ('id', 'version', 'created_at', 'datetime')

    @action(detail=True, methods=['get'], suffix='metadata')
    def metadata(self, request, pk=None):
        build = self.get_object()
        return Response(build.metadata)

    def __enrich_status_details__(self, request, queryset):
        enriched_details = {}
        for tr in queryset:
            try:
                s = tr.status.all()[0]
            except IndexError:
                s = None
            if s:
                if tr.environment.name not in enriched_details.keys():
                    enriched_details[tr.environment.name] = {'testruns': 0,
                                                             'tests_total': 0,
                                                             'tests_pass': 0,
                                                             'tests_fail': 0,
                                                             'tests_xfail': 0,
                                                             'tests_skip': 0}
                enriched_details[tr.environment.name]['testruns'] += 1
                enriched_details[tr.environment.name]['tests_total'] += s.tests_pass + s.tests_fail + s.tests_xfail + s.tests_skip
                enriched_details[tr.environment.name]['tests_pass'] += s.tests_pass
                enriched_details[tr.environment.name]['tests_fail'] += s.tests_fail
                enriched_details[tr.environment.name]['tests_xfail'] += s.tests_xfail
                enriched_details[tr.environment.name]['tests_skip'] += s.tests_skip
        return enriched_details

    @action(detail=True, methods=['get'], suffix='status')
    def status(self, request, pk=None):
        try:
            build = self.get_object()
            qs = build.test_runs.prefetch_related('environment', Prefetch("status", queryset=Status.objects.filter(suite=None)))
            enriched_details = self.__enrich_status_details__(request, qs)
            serializer = ProjectStatusSerializer(build.status, many=False, context={'request': request, 'enriched_details': enriched_details})
            return Response(serializer.data)
        except ProjectStatus.DoesNotExist:
            raise NotFound()

    @action(detail=True, methods=['get'], suffix='test runs')
    def testruns(self, request, pk=None):
        testruns = self.get_object().test_runs.prefetch_related(
            Prefetch("status", queryset=Status.objects.filter(suite=None))
        ).order_by("-id")
        page = self.paginate_queryset(testruns)
        serializer = TestRunSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['get'], suffix='test jobs')
    def testjobs(self, request, pk=None):
        testjobs = self.get_object().test_jobs.order_by('-id')
        page = self.paginate_queryset(testjobs)
        serializer = TestJobSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    def __return_delayed_report(self, request, wait=False):
        force = request.query_params.get("force", False)

        output_format = request.query_params.get("output", "text/plain")
        template_id = request.query_params.get("template", None)
        baseline_id = request.query_params.get("baseline", None)
        email_recipient = request.query_params.get("email_recipient", None)
        callback = request.query_params.get("callback", None)
        callback_token = request.query_params.get("callback_token", None)
        # keep the cached reports for 1 day by default
        data_retention_days = request.query_params.get("keep", 1)
        if request.method == "POST":
            output_format = request.data.get("output", "text/plain")
            template_id = request.data.get("template", None)
            baseline_id = request.data.get("baseline", None)
            email_recipient = request.data.get("email_recipient", None)
            callback = request.data.get("callback", None)
            callback_token = request.data.get("callback_token", None)
            # keep the cached reports for 1 day by default
            data_retention_days = request.data.get("keep", 1)

        template = None
        if template_id != "default":
            template = self.get_object().project.custom_email_template
        if template_id is not None:
            try:
                template = EmailTemplate.objects.get(pk=template_id)
            except EmailTemplate.DoesNotExist:
                pass

        baseline = None

        report_kwargs = {
            "baseline": baseline,
            "template": template,
            "output_format": output_format,
            "email_recipient": email_recipient,
            "callback": callback,
            "callback_token": callback_token,
            "data_retention_days": data_retention_days
        }
        if baseline_id is not None:
            baseline_ok = False
            try:
                previous_build = Build.objects.get(pk=baseline_id)
                report_kwargs["baseline"] = previous_build.status
                baseline_ok = True
            except Build.DoesNotExist:
                data = {"message": "Baseline build %s does not exist" % baseline_id}
            except ProjectStatus.DoesNotExist:
                data = {"message": "Build %s has no status" % baseline_id}

            if not baseline_ok:
                report_kwargs.update({"build": self.get_object()})
                return update_delayed_report(None, data, status.HTTP_400_BAD_REQUEST, **report_kwargs)

        if force:
            delayed_report = self.get_object().delayed_reports.create(**report_kwargs)
            created = True
            log_addition(request, delayed_report, "Force create report")
        else:
            try:
                delayed_report, created = self.get_object().delayed_reports.get_or_create(**report_kwargs)
                if created:
                    log_addition(request, delayed_report, "Create report")
                else:
                    log_change(request, delayed_report, "Update report")
            except core_exceptions.MultipleObjectsReturned:
                delayed_report = self.get_object().delayed_reports.last()
                created = False

        if created:
            if wait:
                delayed_report = prepare_report(delayed_report.pk)
            else:
                prepare_report.delay(delayed_report.pk)

        return delayed_report

    @action(detail=True, methods=['get'], suffix='email')
    def email(self, request, pk=None):
        """
        This method produces the body of email notification for the build.
        By default it uses the project settings for HTML and template.
        These settings can be overwritten by using GET parameters:
         * output - sets the output format (text/plan, text/html)
         * template - sets the template used (id of existing template or
                      "default" for default SQUAD templates)
         * force - force email report re-generation even if there is
                   existing one cached
        """
        delayed_report = self.__return_delayed_report(request, wait=True)
        if delayed_report.status_code != status.HTTP_200_OK:
            return Response(yaml.safe_load(delayed_report.error_message or ''), delayed_report.status_code)
        if delayed_report.output_format == "text/html" and delayed_report.output_html:
            return HttpResponse(delayed_report.output_html, content_type=delayed_report.output_format)
        return HttpResponse(delayed_report.output_text, content_type=delayed_report.output_format)

    @action(detail=True, methods=['get', 'post'], suffix='report', permission_classes=[AllowAny])
    def report(self, request, pk=None):
        delayed_report = self.__return_delayed_report(request)
        data = {"message": "OK", "url": rest_reverse('delayedreport-detail', args=[delayed_report.pk], request=request)}
        return Response(data, status=status.HTTP_202_ACCEPTED)


class EnvironmentSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Environment
        fields = '__all__'


class EnvironmentViewSet(ModelViewSet):
    """
    List of environments. Only environments belonging to public projects and
    projects you have access to are available.
    """
    queryset = Environment.objects
    project_lookup_key = 'project__in'
    serializer_class = EnvironmentSerializer
    filterset_fields = ('project', 'slug', 'name')
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore
    filterset_class = EnvironmentFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore
    search_fields = ('slug', 'name')
    ordering_fields = ('id', 'slug', 'name')


class HyperlinkedMetricsIdentityField(serializers.HyperlinkedIdentityField):
    def get_url(self, *args):
        testrun = args[0]
        statuses = testrun.status.all()
        if len(statuses) > 0:
            if testrun.status.all()[0].has_metrics:
                return super().get_url(*args)
        else:
            return None


class HyperlinkedTestsIdentityField(serializers.HyperlinkedIdentityField):
    def get_url(self, *args):
        testrun = args[0]
        statuses = testrun.status.all()
        if len(statuses) > 0:
            tr_status = testrun.status.all()[0]
            num_tests = (
                tr_status.tests_pass + tr_status.tests_fail + tr_status.tests_skip + tr_status.tests_xfail
            )
            if num_tests > 0:
                return super().get_url(*args)
        else:
            return None


class StatusFilter(filters.FilterSet):
    class Meta:
        model = Status
        fields = {'suite': ['exact', 'isnull'],
                  'metrics_summary': ['gt', 'lt'],
                  'tests_pass': ['gt', 'lt'],
                  'tests_fail': ['gt', 'lt'],
                  'tests_xfail': ['gt', 'lt'],
                  'tests_skip': ['gt', 'lt'],
                  'has_metrics': ['exact'], }


class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Status
        exclude = ('test_run',)


class StatusViewSet(NestedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Status.objects
    serializer_class = StatusSerializer
    filterset_class = StatusFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore


class TestRunSerializer(serializers.HyperlinkedModelSerializer):

    id = serializers.IntegerField(read_only=True)
    tests_file = HyperlinkedTestsIdentityField(view_name='testrun-tests-file')
    metrics_file = HyperlinkedMetricsIdentityField(view_name='testrun-metrics-file')
    metadata_file = serializers.HyperlinkedIdentityField(view_name='testrun-metadata-file')
    log_file = serializers.HyperlinkedIdentityField(view_name='testrun-log-file')
    tests = HyperlinkedTestsIdentityField(view_name='testrun-tests')
    metrics = HyperlinkedMetricsIdentityField(view_name='testrun-metrics')

    class Meta:
        model = TestRun
        fields = '__all__'


class SuiteSerializer(serializers.HyperlinkedModelSerializer):

    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Suite
        exclude = ('metadata',)


class TestNameSerializer(serializers.BaseSerializer):
    name = serializers.CharField(read_only=True)


class SuiteViewSet(viewsets.ModelViewSet):
    """
    Additional actions:

     * `api/suites/<id>/tests` GET

        Returns list of all test belonging to this suite
    """

    queryset = Suite.objects.all()
    serializer_class = SuiteSerializer
    filterset_class = SuiteFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore

    @action(detail=True, methods=['get'], suffix='tests')
    def tests(self, request, pk=None):
        suite = self.get_object()
        tests = Test.objects.filter(suite=suite).prefetch_related('metadata', 'suite', 'known_issues').order_by('id')
        paginator = CursorPaginationWithPageSize()
        page = paginator.paginate_queryset(tests, request)
        serializer = TestSerializer(page, many=True, context={'request': request}, remove_fields=['suite'])
        return paginator.get_paginated_response(serializer.data)


class TestSerializer(serializers.HyperlinkedModelSerializer):

    id = serializers.IntegerField(read_only=True)

    def __init__(self, *args, **kwargs):
        remove_fields = kwargs.pop('remove_fields', None)
        super(TestSerializer, self).__init__(*args, **kwargs)
        if remove_fields:
            # for multiple fields in a list
            for field_name in remove_fields:
                self.fields.pop(field_name)

    name = serializers.CharField(source='full_name', read_only=True)
    short_name = serializers.CharField(source='name')
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Test
        exclude = ['metadata']


class TestViewSet(ModelViewSet):

    queryset = Test.objects.prefetch_related('suite', 'known_issues', 'metadata').all()
    project_lookup_key = 'test_run__build__project__in'
    serializer_class = TestSerializer
    filterset_class = TestFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore
    pagination_class = CursorPaginationWithPageSize
    ordering = ('id',)


class MetricSerializer(serializers.HyperlinkedModelSerializer):

    id = serializers.IntegerField(read_only=True)

    def __init__(self, *args, **kwargs):
        remove_fields = kwargs.pop('remove_fields', None)
        super(MetricSerializer, self).__init__(*args, **kwargs)
        if remove_fields:
            # for multiple fields in a list
            for field_name in remove_fields:
                self.fields.pop(field_name)

    name = serializers.CharField(source='full_name', read_only=True)
    short_name = serializers.CharField(source='name')
    measurement_list = serializers.ListField(read_only=True)

    class Meta:
        model = Metric
        exclude = ['measurements']


class MetricViewSet(ModelViewSet):

    queryset = Metric.objects.prefetch_related('suite').all()
    project_lookup_key = 'test_run__build__project__in'
    serializer_class = MetricSerializer
    filterset_class = MetricFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore
    pagination_class = CursorPaginationWithPageSize
    ordering = ('id',)


class TestRunViewSet(ModelViewSet):
    """
    List of test runs. Test runs represent test executions of a given build on
    a given environment.

    Only test runs from public projects and from projects accessible to you are
    available.

    Additional actions:

     * `api/testruns/<id>/tests_file` GET

        Presents tests_file from original submission

     * `api/testruns/<id>/metrics_file` GET

        Presents metrics_file from original submission

     * `api/testruns/<id>/metadata_file` GET

        Presents metadata_file from original submission

     * `api/testruns/<id>/log_file` GET

        Presents log_file from original submission

     * `api/testruns/<id>/tests` GET

        Returns list of Test objects belonging to this test run. List is paginated

     * `api/testruns/<id>/metrics` GET

        Returns list of Metric objects belonging to this test run. List is paginated

     * `api/testruns/<id>/status` GET

        Presents summary view for each suite present in this test run
    """
    queryset = TestRun.objects.prefetch_related(
        Prefetch("status", queryset=Status.objects.filter(suite=None))
    ).order_by("-id")
    project_lookup_key = 'build__project__in'
    serializer_class = TestRunSerializer
    filterset_fields = (
        "build",
        "completed",
        "job_status",
        "data_processed",
        "status_recorded",
        "environment",
    )
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore
    filterset_class = TestRunFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore
    search_fields = ('environment',)
    ordering_fields = ('id', 'created_at', 'environment', 'datetime')
    pagination_class = CursorPaginationWithPageSize
    ordering = ('id',)

    @action(detail=True, methods=['get'])
    def tests_file(self, request, pk=None):
        testrun = self.get_object()
        return HttpResponse(testrun.tests_file, content_type='application/json')

    @action(detail=True, methods=['get'])
    def metrics_file(self, request, pk=None):
        testrun = self.get_object()
        return HttpResponse(testrun.metrics_file, content_type='application/json')

    @action(detail=True, methods=['get'])
    def metadata_file(self, request, pk=None):
        testrun = self.get_object()
        return HttpResponse(testrun.metadata_file, content_type='application/json')

    @action(detail=True, methods=['get'])
    def log_file(self, request, pk=None):
        testrun = self.get_object()
        return HttpResponse(testrun.log_file, content_type='text/plain')

    @action(detail=True, methods=['get'], suffix='tests')
    def tests(self, request, pk=None):
        testrun = self.get_object()
        tests = testrun.tests.prefetch_related('suite', 'known_issues', 'metadata').order_by('id')
        paginator = CursorPaginationWithPageSize()
        page = paginator.paginate_queryset(tests, request)
        serializer = TestSerializer(page, many=True, context={'request': request}, remove_fields=['test_run'])
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=['get'], suffix='metrics')
    def metrics(self, request, pk=None):
        testrun = self.get_object()
        metrics = testrun.metrics.prefetch_related('suite').order_by('id')
        paginator = CursorPaginationWithPageSize()
        page = paginator.paginate_queryset(metrics, request)
        serializer = MetricSerializer(page, many=True, context={'request': request}, remove_fields=['test_run', 'id', 'suite'])
        return paginator.get_paginated_response(serializer.data)


class BackendSerializer(serializers.HyperlinkedModelSerializer):

    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Backend
        fields = '__all__'
        extra_kwargs = {
            'token': {'write_only': True}
        }


class BackendViewSet(viewsets.ModelViewSet):
    """
    List of CI backends used.
    """
    queryset = Backend.objects.all()
    serializer_class = BackendSerializer
    filterset_fields = ('implementation_type', 'name', 'url')
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore
    search_fields = ('implementation_type', 'name', 'url')
    ordering_fields = ('id', 'implementation_type', 'name', 'url')


class TestJobSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField(read_only=True)
    url = serializers.HyperlinkedIdentityField(view_name='testjob-detail')
    external_url = serializers.CharField(source='url', read_only=True)
    definition = serializers.HyperlinkedIdentityField(view_name='testjob-definition')

    class Meta:
        model = TestJob
        fields = '__all__'


class TestJobViewSet(ModelViewSet):
    """
    List of CI test jobs. Only testjobs for public projects, and for projects
    you have access to, are available.

    Additional actions:

     * `api/testjobs/<id>/definition` GET

        Presents original test job definition

     * `api/testjobs/<id>/resubmit` POST

        Allows to resubmit the job. Will produce new test job using the same backend

     * `api/testjobs/<id>/force_resubmit` POST

        Same as 'resubmit' but can be done also on successful jobs

     * `api/testjobs/<id>/cancel` POST

        Allows to cancel a job
    """
    queryset = TestJob.objects.prefetch_related('backend').order_by('-id').defer('definition')
    project_lookup_key = 'target_build__project__in'
    serializer_class = TestJobSerializer
    filterset_fields = (
        "name",
        "environment",
        "submitted",
        "fetched",
        "fetch_attempts",
        "last_fetch_attempt",
        "failure",
        "can_resubmit",
        "resubmitted_count",
        "job_status",
        "job_id",
        "backend",
        "target",
        "testrun",
    )
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore
    filterset_class = TestJobFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore
    search_fields = ("name", "environment", "last_fetch_attempt")
    ordering_fields = ("id", "name", "environment", "last_fetch_attempt")
    pagination_class = CursorPaginationWithPageSize
    ordering = ('id',)

    @action(detail=True, methods=['get'], suffix='definition')
    def definition(self, request, pk=None):
        definition = self.get_object().definition
        return HttpResponse(definition, content_type='text/plain')

    @action(detail=True, methods=['post'], suffix='resubmit')
    def resubmit(self, request, **kwargs):
        testjob = self.get_object()
        if testjob.resubmit():
            # find latest child of this job
            new_testjob = testjob.resubmitted_jobs.last()
            log_addition(request, new_testjob, "Created testjob as resubmission")
            data = {"message": "OK", "url": rest_reverse('testjob-detail', args=[new_testjob.pk], request=request)}
            return Response(data, status=status.HTTP_200_OK)
        return Response(
            {"message": "Error resubmitting job.",
             "url": rest_reverse("testjob-detail", args=[testjob.pk], request=request)},
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], suffix='force_resubmit')
    def force_resubmit(self, request, **kwargs):
        testjob = self.get_object()
        if testjob.force_resubmit():
            # find latest child of this job
            new_testjob = testjob.resubmitted_jobs.last()
            log_addition(request, new_testjob, "Created testjob as resubmission")
            data = {"message": "OK", "url": rest_reverse('testjob-detail', args=[new_testjob.pk], request=request)}
            return Response(data, status=status.HTTP_200_OK)
        return Response(
            {"message": "Error resubmitting job.",
             "url": rest_reverse("testjob-detail", args=[testjob.pk], request=request)},
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], suffix='cancel')
    def cancel(self, request, **kwargs):
        testjob = self.get_object()
        testjob.cancel()
        log_change(request, testjob, "Testjob cancelled")
        return Response({'job_id': testjob.job_id, 'status': testjob.job_status}, status=status.HTTP_200_OK)


class EmailTemplateSerializer(serializers.HyperlinkedModelSerializer):

    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = EmailTemplate
        fields = '__all__'


class EmailTemplateViewSet(viewsets.ModelViewSet):
    """
    List of email templates used.
    """
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    filterset_fields = ('name',)
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore
    ordering_fields = ('name', 'id')


class KnownIssueSerializer(serializers.HyperlinkedModelSerializer):

    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = KnownIssue
        fields = '__all__'


class KnownIssueViewSet(viewsets.ModelViewSet):

    queryset = KnownIssue.objects.prefetch_related('environments').all()
    serializer_class = KnownIssueSerializer
    filterset_class = KnownIssueFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore
    filterset_fields = ('title', 'test_name', 'active', 'intermittent', 'environments')
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore
    ordering_fields = ('title', 'id')


class AnnotationSerializer(serializers.HyperlinkedModelSerializer):

    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Annotation
        fields = '__all__'


class AnnotationViewSet(viewsets.ModelViewSet):

    queryset = Annotation.objects.all()
    serializer_class = AnnotationSerializer
    filterset_fields = ('description', 'build')
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore
    ordering_fields = ('id', 'build')


class MetricThresholdSerializer(serializers.HyperlinkedModelSerializer):

    id = serializers.IntegerField(read_only=True)

    class Meta:
        model = MetricThreshold
        fields = '__all__'


class MetricThresholdViewSet(viewsets.ModelViewSet):

    queryset = MetricThreshold.objects.all()
    serializer_class = MetricThresholdSerializer
    filterset_fields = ('name', 'value', 'is_higher_better', 'environment')
    filter_fields = filterset_fields  # TODO: remove when django-filters 1.x is not supported anymore
    ordering_fields = ('id', 'environment', 'name')
    filterset_class = MetricThresholdFilter
    filter_class = filterset_class  # TODO: remove when django-filters 1.x is not supported anymore


router = APIRouter()
router.register(r'groups', GroupViewSet)
router.register(r'projects', ProjectViewSet)
router.register(r'builds', BuildViewSet)
router.register(r'testjobs', TestJobViewSet)
router.register(r'testruns', TestRunViewSet).register(
    r'status',
    StatusViewSet,
    parents_query_lookups=['test_run_id'],
    **drf_basename('testrun-status')
)
router.register(r'tests', TestViewSet)
router.register(r'metrics', MetricViewSet)
router.register(r'suites', SuiteViewSet)
router.register(r'environments', EnvironmentViewSet)
router.register(r'backends', BackendViewSet)
router.register(r'emailtemplates', EmailTemplateViewSet)
router.register(r'knownissues', KnownIssueViewSet)
router.register(r'patchsources', PatchSourceViewSet)
router.register(r'suitemetadata', SuiteMetadataViewset)
router.register(r'annotations', AnnotationViewSet)
router.register(r'metricthresholds', MetricThresholdViewSet)
router.register(r'reports', DelayedReportViewSet)
