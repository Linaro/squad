from squad.core.models import Project
from rest_framework import routers, serializers, viewsets


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Project
        fields = (
            'url',
            'full_name',
            'slug',
            'name',
            'is_public',
            'description',
        )


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects
    serializer_class = ProjectSerializer

    def get_queryset(self):
        return self.queryset.accessible_to(self.request.user)


router = routers.DefaultRouter()
router.register(r'projects', ProjectViewSet)
