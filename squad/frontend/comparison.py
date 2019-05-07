from django.shortcuts import render
from django.core.paginator import Paginator

from squad.core.models import Project
from squad.core.comparison import TestComparison


def compare_projects(request):
    user = request.user
    projects = Project.objects.accessible_to(user).prefetch_related('group')
    selected = [p for p in projects if p.full_name in request.GET.getlist('project')]

    if len(selected) > 1:
        comparison = TestComparison.compare_projects(*selected)

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
    }

    return render(request, 'squad/compare_projects.jinja2', context)


def compare_test(request):

    context = {}
    return render(request, 'squad/compare.jinja2', context)
