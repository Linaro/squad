import django_filters
from django.core.paginator import Paginator, EmptyPage
from django.shortcuts import render
from django.http import Http404
from django.utils.translation import gettext_lazy as N_

from squad.http import auth
from squad.ci.models import TestJob


class TestjobFilter(django_filters.FilterSet):
    has_errors = django_filters.BooleanFilter(field_name='failure', lookup_expr='isnull', label=N_('Success'))
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains', label=N_('Name'))
    job_status = django_filters.CharFilter(field_name='job_status', lookup_expr='iexact', label=N_('Job Status'))
    submitted = django_filters.BooleanFilter(field_name='submitted', lookup_expr='exact', label=N_('Is submitted'))
    fetched = django_filters.BooleanFilter(field_name='fetched', lookup_expr='exact', label=N_('Is Fetched'))
    job_id = django_filters.CharFilter(field_name='job_id', lookup_expr='icontains', label=N_('Job ID'))
    environment = django_filters.CharFilter(field_name='environment', lookup_expr='icontains', label=N_('Environment'))

    class Meta:
        model = TestJob
        fields = ['name', 'job_status', 'submitted', 'fetched', 'job_id', 'environment']


@auth
def testjobs(request, group_slug, project_slug, build_version):
    project = request.project
    build = project.builds.filter(version=build_version).prefetch_related('annotation').last()
    if build is None:
        raise Http404()

    testjobs = TestJob.objects.filter(target_build=build).prefetch_related('backend', 'parent_job__backend').defer('definition').order_by('id')

    try:
        testjob_filter = TestjobFilter(request.GET, queryset=testjobs)
        page = request.GET.get('page', 1)
        per_page = request.GET.get('per_page', 25)
        paginator = Paginator(testjob_filter.qs, per_page)
        testjobs_page = paginator.page(page)
        context = {
            'filter': testjob_filter,
            "project": project,
            "build": build,
            "testjobs": testjobs_page,
            "user_can_submit_jobs": project.can_submit_testjobs(request.user),
        }

        return render(request, 'squad/testjobs.jinja2', context)
    except EmptyPage:
        raise Http404()
