from squad.core.models import Project, Build, TestRun, Environment
from squad.ci.models import Backend, TestJob
from django.http import HttpResponse
from rest_framework import routers, serializers, viewsets
from rest_framework.decorators import detail_route
from rest_framework.response import Response


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

    class Meta:
        model = Project
        fields = (
            'url',
            'full_name',
            'slug',
            'name',
            'is_public',
            'description',
            'builds',
        )


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects
    serializer_class = ProjectSerializer

    def get_queryset(self):
        return self.queryset.accessible_to(self.request.user)

    @detail_route(methods=['get'])
    def builds(self, request, pk=None):
        builds = self.get_object().builds.order_by('-datetime')
        page = self.paginate_queryset(builds)
        serializer = BuildSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)


class BuildSerializer(serializers.HyperlinkedModelSerializer):
    testruns = serializers.HyperlinkedIdentityField(view_name='build-testruns')
    testjobs = serializers.HyperlinkedIdentityField(view_name='build-testjobs')

    class Meta:
        model = Build
        fields = '__all__'


class BuildViewSet(ModelViewSet):
    queryset = Build.objects.all()
    serializer_class = BuildSerializer

    def get_queryset(self):
        return self.queryset.filter(project__in=self.get_project_ids())

    @detail_route(methods=['get'])
    def testruns(self, request, pk=None):
        testruns = self.get_object().test_runs.order_by('-id')
        page = self.paginate_queryset(testruns)
        serializer = TestRunSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @detail_route(methods=['get'])
    def testjobs(self, request, pk=None):
        testjobs = self.get_object().test_jobs.order_by('-id')
        page = self.paginate_queryset(testjobs)
        serializer = TestJobSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)


class EnvironmentSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Environment
        fields = '__all__'


class EnvironmentViewSet(ModelViewSet):
    queryset = Environment.objects
    serializer_class = EnvironmentSerializer

    def get_queryset(self):
        return self.queryset.filter(project__in=self.get_project_ids())


class TestRunSerializer(serializers.HyperlinkedModelSerializer):

    tests_file = serializers.HyperlinkedIdentityField(view_name='testrun-tests-file')
    metrics_file = serializers.HyperlinkedIdentityField(view_name='testrun-metrics-file')
    metadata_file = serializers.HyperlinkedIdentityField(view_name='testrun-metadata-file')
    log_file = serializers.HyperlinkedIdentityField(view_name='testrun-log-file')

    class Meta:
        model = TestRun
        fields = '__all__'


class TestRunViewSet(ModelViewSet):
    queryset = TestRun.objects.order_by('-id')
    serializer_class = TestRunSerializer

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


class BackendSerializer(serializers.ModelSerializer):
    class Meta:
        model = Backend
        exclude = ('token',)


class BackendViewSet(viewsets.ModelViewSet):
    queryset = Backend.objects.all()
    serializer_class = BackendSerializer


class TestJobSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='testjob-detail')
    external_url = serializers.CharField(source='url', read_only=True)
    definition = serializers.HyperlinkedIdentityField(view_name='testjob-definition')

    class Meta:
        model = TestJob
        fields = '__all__'


class TestJobViewSet(ModelViewSet):
    queryset = TestJob.objects.order_by('-id')
    serializer_class = TestJobSerializer

    def get_queryset(self):
        return self.queryset.filter(target_build__project__in=self.get_project_ids())

    @detail_route(methods=['get'])
    def definition(self, request, pk=None):
        definition = self.get_object().definition
        return HttpResponse(definition, content_type='text/plain')


router = routers.DefaultRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'builds', BuildViewSet)
router.register(r'testjobs', TestJobViewSet)
router.register(r'testruns', TestRunViewSet)
router.register(r'environments', EnvironmentViewSet)
router.register(r'backends', BackendViewSet)
