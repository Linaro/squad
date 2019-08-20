from functools import reduce

from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch

from squad.core.models import Project, Group, Build
from squad.core.comparison import TestComparison, MetricComparison
from squad.frontend.utils import alphanum_sort


RESULT_STATES = ['pass', 'fail', 'xfail', 'skip', 'n/a']
TRANSITIONS = {(_from, _to): False for _from in RESULT_STATES for _to in RESULT_STATES}
DEFAULT_CHECKED_TRANSITIONS = [('pass', 'fail'), ('fail', 'pass')]


def __get_comparison_class(comparison_type):
    if 'metric' == comparison_type:
        return MetricComparison
    else:
        return TestComparison


def __paginate(results, request):
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    paginator = Paginator(tuple(results.items()), 50)
    return paginator.page(page)


def __get_transitions(request):
    transitions = TRANSITIONS.copy()
    marked_transitions = request.GET.getlist('transitions', [])

    if 'ignore' in marked_transitions:
        return {}

    if len(marked_transitions) > 0:
        for t in marked_transitions:
            _from, _to = t.split(':')
            if _from in RESULT_STATES and _to in RESULT_STATES:
                transitions[(_from, _to)] = True
    else:
        for default in DEFAULT_CHECKED_TRANSITIONS:
            transitions[(default[0], default[1])] = True

    return transitions


def compare_projects(request):
    comparison = None
    group = None
    projects = None
    comparison_type = request.GET.get('comparison_type', 'test')
    transitions = __get_transitions(request)
    group_slug = request.GET.get('group')

    if group_slug:
        group = get_object_or_404(Group, slug=group_slug)
        qs = group.projects.accessible_to(request.user).prefetch_related(
            Prefetch('builds', queryset=Build.objects.order_by('-datetime'))
        )
        projects = alphanum_sort(qs, 'slug')

        filters = []
        for key, value in request.GET.items():
            if 'project_' in key and len(key.split('_')) == 2:
                project_id = key.split('_')[1]
                filters.append(Q(project_id=project_id) & Q(version=value))

        if len(filters) > 1:
            build_filters = reduce(lambda x, y: x | y, filters)
            builds = Build.objects.filter(build_filters)
            comparison_class = __get_comparison_class(comparison_type)
            comparison = comparison_class.compare_builds(*builds)

            if comparison_type == 'test' and len(transitions):
                comparison.apply_transitions([t for t, checked in transitions.items() if checked])

            comparison.results = __paginate(comparison.results, request)

    context = {
        'group': group,
        'projects': projects,
        'comparison': comparison,
        'comparison_type': comparison_type,
        'transitions': transitions,
    }

    return render(request, 'squad/compare_projects.jinja2', context)


def compare_test(request):

    context = {}
    return render(request, 'squad/compare.jinja2', context)


def compare_builds(request):
    project_slug = request.GET.get('project')
    comparison_type = request.GET.get('comparison_type', 'test')
    transitions = __get_transitions(request)
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

            if comparison_type == 'test' and len(transitions):
                comparison.apply_transitions([t for t, checked in transitions.items() if checked])

            comparison.results = __paginate(comparison.results, request)

    context = {
        'project': project,
        'comparison': comparison,
        'comparison_type': comparison_type,
        'transitions': transitions,
    }

    return render(request, 'squad/compare_builds.jinja2', context)
