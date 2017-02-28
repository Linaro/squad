from django.shortcuts import render

from squad.http import auth
from squad.core.models import Group
from squad.core.comparison import TestComparison
from squad.core.history import TestHistory


@auth
def tests(request, group_slug, project_slug):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)

    build = project.builds.last()
    comparison = TestComparison(build)
    context = {
        "project": project,
        "comparison": comparison,
    }
    return render(request, 'squad/tests.html', context)


@auth
def test_history(request, group_slug, project_slug, full_test_name):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)

    history = TestHistory(project, full_test_name)
    context = {
        "project": project,
        "history": history,
    }
    return render(request, 'squad/test_history.html', context)
