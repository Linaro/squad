from squad.core.models import Project, Build
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
    class Meta:
        model = Build
        fields = '__all__'


class BuildViewSet(ModelViewSet):
    queryset = Build.objects.all()
    serializer_class = BuildSerializer

    def get_queryset(self):
        return self.queryset.filter(project__in=self.get_project_ids())


router = routers.DefaultRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'builds', BuildViewSet)
