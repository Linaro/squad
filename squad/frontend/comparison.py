from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator

from squad.core.models import Project
from squad.core.comparison import TestComparison, MetricComparison


def __get_comparison_class(comparison_type):
    if 'metric' == comparison_type:
        return MetricComparison
    else:
        return TestComparison


def compare_projects(request):
    user = request.user
    projects = Project.objects.accessible_to(user).prefetch_related('group')
    selected = [p for p in projects if p.full_name in request.GET.getlist('project')]
    comparison_type = request.GET.get('comparison_type', 'test')

    if len(selected) > 1:
        comparison_class = __get_comparison_class(comparison_type)
        comparison = comparison_class.compare_projects(*selected)

        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1
        paginator = Paginator(tuple(comparison.results.items()), 50)
        comparison.results = paginator.page(page)
    else:
        comparison = None

    context = {
        'projects': projects,
        'selected': selected,
        'comparison': comparison,
        'comparison_type': comparison_type,
    }

    return render(request, 'squad/compare_projects.jinja2', context)


def compare_test(request):

    context = {}
    return render(request, 'squad/compare.jinja2', context)


def compare_builds(request):
    project_slug = request.GET.get('project')
    comparison_type = request.GET.get('comparison_type', 'test')
    comparison = None
    project = None
    if project_slug:
        group_slug, project_slug = project_slug.split('/')
        project = get_object_or_404(Project, group__slug=group_slug, slug=project_slug)

        baseline_build = request.GET.get('baseline')
        target_build = request.GET.get('target')
        if baseline_build and target_build:
            baseline = get_object_or_404(project.builds, version=baseline_build)
            target = get_object_or_404(project.builds, version=target_build)

            comparison_class = __get_comparison_class(comparison_type)
            comparison = comparison_class.compare_builds(baseline, target)

            try:
                page = int(request.GET.get('page', '1'))
            except ValueError:
                page = 1
            paginator = Paginator(tuple(comparison.results.items()), 50)
            comparison.results = paginator.page(page)

    context = {
        'project': project,
        'comparison': comparison,
        'comparison_type': comparison_type,
    }

    return render(request, 'squad/compare_builds.jinja2', context)
