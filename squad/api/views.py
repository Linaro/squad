from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse


from squad.core.models import Group
from squad.core.models import Project
from squad.core.models import Build
from squad.core.models import Environment
from squad.core.models import TestRun


@csrf_exempt
@require_http_methods(["POST"])
def add_test_run(request, group_slug, project_slug, version, environment_slug):
    # FIXME ADD AUTHENTICATION
    group, _ = Group.objects.get_or_create(slug=group_slug)
    project, _ = group.projects.get_or_create(slug=project_slug)
    build, _ = project.builds.get_or_create(version=version)
    environment, _ = project.environments.get_or_create(slug=environment_slug)

    test_run = build.test_runs.create(environment=environment)

    if 'tests' in request.FILES:
        data = bytes()
        f = request.FILES['tests']
        for chunk in f.chunks():
            data = data + chunk
        test_run.tests_file = data
    if 'benchmarks' in request.FILES:
        data = bytes()
        f = request.FILES['benchmarks']
        for chunk in f.chunks():
            data = data + chunk
        test_run.benchmarks_file = data
    if 'log' in request.FILES:
        data = bytes()
        f = request.FILES['log']
        for chunk in f.chunks():
            data = data + chunk
        test_run.log_file = data

    test_run.save()

    return HttpResponse('', status=201)
