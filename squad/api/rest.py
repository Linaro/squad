from squad.core.models import Project, ProjectStatus, Build, TestRun, Environment, Test, Metric, EmailTemplate
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


class ProjectSerializer(serializers.HyperlinkedModelSerializer):

    builds = serializers.HyperlinkedIdentityField(
        view_name='project-builds',
    )
    slug = serializers.CharField(read_only=True)

    class Meta:
        model = Project
        fields = (
            'url',
            'id',
            'full_name',
            'slug',
            'name',
            'is_public',
            'description',
            'builds',
        )


class ProjectViewSet(viewsets.ModelViewSet):
    """
    List of projects. Includes public projects and projects that the current
    user has access to.
    """
    queryset = Project.objects
    serializer_class = ProjectSerializer
    filter_fields = ('group', 'slug', 'name')

    def get_queryset(self):
        return self.queryset.accessible_to(self.request.user)

    @detail_route(methods=['get'], suffix='builds')
    def builds(self, request, pk=None):
        """
        List of builds for the current project.
        """
        builds = self.get_object().builds.order_by('-datetime')
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
                  'build')


class ProjectStatusViewSet(viewsets.ModelViewSet):
    queryset = ProjectStatus.objects
    serializer_class = ProjectStatusSerializer
    filter_fields = ('build',)


class BuildSerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.IntegerField()
    testruns = serializers.HyperlinkedIdentityField(view_name='build-testruns')
    testjobs = serializers.HyperlinkedIdentityField(view_name='build-testjobs')
    # not sure if 'finished' field is needed when status is exposed
    finished = serializers.BooleanField(read_only=True)
    status = serializers.HyperlinkedIdentityField(read_only=True, view_name='build-status', allow_null=True)

    class Meta:
        model = Build
        fields = '__all__'


class BuildViewSet(ModelViewSet):
    """
    List of all builds in the system. Only builds belonging to public projects
    and to projects you have access to are available.
    """
    queryset = Build.objects.all()
    serializer_class = BuildSerializer
    filter_fields = ('version', 'project')

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
        "completed",
        "job_status",
        "data_processed",
        "status_recorded",
        "environment",
    )

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
        exclude = ('token',)


class BackendViewSet(viewsets.ModelViewSet):
    """
    List of CI backends used.
    """
    queryset = Backend.objects.all()
    serializer_class = BackendSerializer
    filter_fields = ('implementation_type',)


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
        "failure",
        "can_resubmit",
        "resubmitted_count",
        "job_status",
        "backend",
        "target",
    )

    def get_queryset(self):
        return self.queryset.filter(target_build__project__in=self.get_project_ids())

    @detail_route(methods=['get'], suffix='definition')
    def definition(self, request, pk=None):
        definition = self.get_object().definition
        return HttpResponse(definition, content_type='text/plain')


class EmailTemplateSerializer(serializers.ModelSerializer):

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


router = APIRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'builds', BuildViewSet)
router.register(r'testjobs', TestJobViewSet)
router.register(r'testruns', TestRunViewSet)
router.register(r'environments', EnvironmentViewSet)
router.register(r'backends', BackendViewSet)
router.register(r'emailtemplates', EmailTemplateViewSet)
