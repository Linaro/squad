from django.contrib.auth.models import Group as UserGroup
from squad.core.models import Group, Project, ProjectStatus, Build, TestRun, Environment, Test, Metric, EmailTemplate
from squad.core.notification import Notification
from squad.ci.models import Backend, TestJob
from django.http import HttpResponse
from rest_framework import routers, serializers, views, viewsets
from rest_framework.decorators import detail_route
from rest_framework.exceptions import NotFound
from rest_framework.response import Response


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
    """

    def get_view_name(self):
        return "API"


class APIRouter(routers.DefaultRouter):

    APIRootView = API


class ModelViewSet(viewsets.ModelViewSet):

    def get_project_ids(self):
        """
        Determines which projects the current user is allowed to visualize.
        Returns a list of project ids to be used in get_queryset() for
        filtering.
        """
        user = self.request.user
        projects = Project.objects.accessible_to(user).values('id')
        return [p['id'] for p in projects]


class UserGroupSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = UserGroup
        fields = ('id', 'name', 'url')


class UserGroupViewSet(viewsets.ModelViewSet):
    """
    List of user groups.
    """
    queryset = UserGroup.objects
    serializer_class = UserGroupSerializer
    filter_fields = ('name',)
    search_fields = ('name',)
    ordering_fields = ('name',)


class GroupSerializer(serializers.HyperlinkedModelSerializer):

    id = serializers.IntegerField()
    user_groups = serializers.HyperlinkedRelatedField(
        many=True,
        read_only=True,
        view_name='usergroups-detail')

    class Meta:
        model = Group
        fields = '__all__'


class GroupViewSet(viewsets.ModelViewSet):
    """
    List of groups. Includes public groups and groups that the current
    user has access to.
    """
    queryset = Group.objects
    serializer_class = GroupSerializer
    filter_fields = ('slug', 'name')
    search_fields = ('slug', 'name')
    ordering_fields = ('slug', 'name')

#    def get_queryset(self):
#        return self.queryset.accessible_to(self.request.user)


class ProjectSerializer(serializers.HyperlinkedModelSerializer):

    builds = serializers.HyperlinkedIdentityField(
        view_name='project-builds',
    )
    slug = serializers.CharField(read_only=True)
    id = serializers.IntegerField()

    class Meta:
        model = Project
        fields = '__all__'


class ProjectViewSet(viewsets.ModelViewSet):
    """
    List of projects. Includes public projects and projects that the current
    user has access to.
    """
    queryset = Project.objects
    serializer_class = ProjectSerializer
    filter_fields = ('group',
                     'slug',
                     'name',
                     'is_public',
                     'html_mail',
                     'custom_email_template',
                     'moderate_notifications',
                     'notification_strategy')
    search_fields = ('slug',
                     'name',)
    ordering_fields = ('slug',
                       'name',)

    def get_queryset(self):
        return self.queryset.accessible_to(self.request.user)

    @detail_route(methods=['get'], suffix='builds')
    def builds(self, request, pk=None):
        """
        List of builds for the current project.
        """
        builds = self.get_object().builds.prefetch_related('test_runs').order_by('-datetime')
        page = self.paginate_queryset(builds)
        serializer = BuildSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)


class ProjectStatusSerializer(serializers.HyperlinkedModelSerializer):
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
                  'has_metrics',
                  'metrics_summary',
                  'build',
                  'created_at')


class ProjectStatusViewSet(viewsets.ModelViewSet):
    queryset = ProjectStatus.objects
    serializer_class = ProjectStatusSerializer
    filter_fields = ('build',)
    ordering_fields = ('created_at', 'last_updated')


class BuildSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField()
    testruns = serializers.HyperlinkedIdentityField(view_name='build-testruns')
    testjobs = serializers.HyperlinkedIdentityField(view_name='build-testjobs')
    status = serializers.HyperlinkedIdentityField(read_only=True, view_name='build-status', allow_null=True)
    metadata = serializers.JSONField(read_only=True)

    class Meta:
        model = Build
        fields = '__all__'


class BuildViewSet(ModelViewSet):
    """
    List of all builds in the system. Only builds belonging to public projects
    and to projects you have access to are available.
    """
    queryset = Build.objects.prefetch_related('test_runs').all()
    serializer_class = BuildSerializer
    filter_fields = ('version', 'project')
    search_fields = ('version',)
    ordering_fields = ('id', 'version', 'created_at', 'datetime')

    def get_queryset(self):
        return self.queryset.filter(project__in=self.get_project_ids())

    @detail_route(methods=['get'], suffix='status')
    def status(self, request, pk=None):
        try:
            status = self.get_object().status
            serializer = ProjectStatusSerializer(status, many=False, context={'request': request})
            return Response(serializer.data)
        except ProjectStatus.DoesNotExist:
            raise NotFound()

    @detail_route(methods=['get'], suffix='test runs')
    def testruns(self, request, pk=None):
        testruns = self.get_object().test_runs.order_by('-id')
        page = self.paginate_queryset(testruns)
        serializer = TestRunSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @detail_route(methods=['get'], suffix='test jobs')
    def testjobs(self, request, pk=None):
        testjobs = self.get_object().test_jobs.order_by('-id')
        page = self.paginate_queryset(testjobs)
        serializer = TestJobSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @detail_route(methods=['get'], suffix='email')
    def email(self, request, pk=None):
        """
        This method produces the body of email notification for the build.
        By default it uses the project settings for HTML and template.
        These settings can be overwritten by using GET parameters:
         * output - sets the output format (text/plan, text/html)
         * template - sets the template used (id of existing template or
                      "default" for default SQUAD templates)
        """
        output_format = request.query_params.get("output", "text/plain")
        template_id = request.query_params.get("template", None)
        template = None
        if template_id != "default":
            template = self.get_object().project.custom_email_template
        if template_id is not None:
            try:
                template = EmailTemplate.objects.get(pk=template_id)
            except EmailTemplate.DoesNotExist:
                pass
        status = self.get_object().status
        notification = Notification(status)
        produce_html = self.get_object().project.html_mail
        if output_format == "text/html":
            produce_html = True
        txt, html = notification.message(produce_html, template)
        if len(html) > 0:
            return HttpResponse(html, content_type=output_format)
        return HttpResponse(txt, content_type=output_format)


class EnvironmentSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField()

    class Meta:
        model = Environment
        fields = '__all__'


class EnvironmentViewSet(ModelViewSet):
    """
    List of environments. Only environments belonging to public projects and
    projects you have access to are available.
    """
    queryset = Environment.objects
    serializer_class = EnvironmentSerializer
    filter_fields = ('project', 'slug', 'name')
    search_fields = ('slug', 'name')
    ordering_fields = ('id', 'slug', 'name')

    def get_queryset(self):
        return self.queryset.filter(project__in=self.get_project_ids())


class TestRunSerializer(serializers.HyperlinkedModelSerializer):

    id = serializers.IntegerField()
    tests_file = serializers.HyperlinkedIdentityField(view_name='testrun-tests-file')
    metrics_file = serializers.HyperlinkedIdentityField(view_name='testrun-metrics-file')
    metadata_file = serializers.HyperlinkedIdentityField(view_name='testrun-metadata-file')
    log_file = serializers.HyperlinkedIdentityField(view_name='testrun-log-file')
    tests = serializers.HyperlinkedIdentityField(view_name='testrun-tests')
    metrics = serializers.HyperlinkedIdentityField(view_name='testrun-metrics')

    class Meta:
        model = TestRun
        fields = '__all__'


class TestSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='full_name', read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Test
        exclude = ('id', 'suite', 'test_run',)


class MetricSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='full_name', read_only=True)
    measurement_list = serializers.ListField(read_only=True)

    class Meta:
        model = Metric
        exclude = ('id', 'name', 'suite', 'test_run', 'measurements')


class TestRunViewSet(ModelViewSet):
    """
    List of test runs. Test runs represent test executions of a given build on
    a given environment.

    Only test runs from public projects and from projects accessible to you are
    available.
    """
    queryset = TestRun.objects.order_by('-id')
    serializer_class = TestRunSerializer
    filter_fields = (
        "build",
        "completed",
        "job_status",
        "data_processed",
        "status_recorded",
        "environment",
    )
    search_fields = ('environment',)
    ordering_fields = ('id', 'created_at', 'environment', 'datetime')

    def get_queryset(self):
        return self.queryset.filter(build__project__in=self.get_project_ids())

    @detail_route(methods=['get'])
    def tests_file(self, request, pk=None):
        testrun = self.get_object()
        return HttpResponse(testrun.tests_file, content_type='application/json')

    @detail_route(methods=['get'])
    def metrics_file(self, request, pk=None):
        testrun = self.get_object()
        return HttpResponse(testrun.metrics_file, content_type='application/json')

    @detail_route(methods=['get'])
    def metadata_file(self, request, pk=None):
        testrun = self.get_object()
        return HttpResponse(testrun.metadata_file, content_type='application/json')

    @detail_route(methods=['get'])
    def log_file(self, request, pk=None):
        testrun = self.get_object()
        return HttpResponse(testrun.log_file, content_type='text/plain')

    @detail_route(methods=['get'], suffix='tests')
    def tests(self, request, pk=None):
        testrun = self.get_object()
        tests = testrun.tests.prefetch_related('suite')
        page = self.paginate_queryset(tests)
        serializer = TestSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @detail_route(methods=['get'], suffix='metrics')
    def metrics(self, request, pk=None):
        testrun = self.get_object()
        metrics = testrun.metrics.prefetch_related('suite')
        page = self.paginate_queryset(metrics)
        serializer = MetricSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)


class BackendSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()

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
    filter_fields = ('implementation_type', 'name', 'url')
    search_fields = ('implementation_type', 'name', 'url')
    ordering_fields = ('id', 'implementation_type', 'name', 'url')


class TestJobSerializer(serializers.HyperlinkedModelSerializer):
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
    """
    queryset = TestJob.objects.order_by('-id')
    serializer_class = TestJobSerializer
    filter_fields = (
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
        "backend",
        "target",
    )
    search_fields = ("name", "environment", "last_fetch_attempt")
    ordering_fields = ("id", "name", "environment", "last_fetch_attempt")

    def get_queryset(self):
        return self.queryset.filter(target_build__project__in=self.get_project_ids())

    @detail_route(methods=['get'], suffix='definition')
    def definition(self, request, pk=None):
        definition = self.get_object().definition
        return HttpResponse(definition, content_type='text/plain')


class EmailTemplateSerializer(serializers.HyperlinkedModelSerializer):

    id = serializers.IntegerField()

    class Meta:
        model = EmailTemplate
        fields = '__all__'


class EmailTemplateViewSet(viewsets.ModelViewSet):
    """
    List of email templates used.
    """
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    filter_fields = ('name',)
    ordering_fields = ('name', 'id')


router = APIRouter()
router.register(r'groups', GroupViewSet)
router.register(r'usergroups', UserGroupViewSet, 'usergroups')
router.register(r'projects', ProjectViewSet)
router.register(r'builds', BuildViewSet)
router.register(r'testjobs', TestJobViewSet)
router.register(r'testruns', TestRunViewSet)
router.register(r'environments', EnvironmentViewSet)
router.register(r'backends', BackendViewSet)
router.register(r'emailtemplates', EmailTemplateViewSet)
