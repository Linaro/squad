from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseForbidden
from django.http import HttpResponse


from squad.core.models import Group
from squad.core.models import Project
from squad.core.models import Build
from squad.core.models import Environment
from squad.core.models import TestRun
from squad.core.models import Token


from squad.core.tasks import ReceiveTestRun


def valid_token(token, project):
    return project.tokens.filter(key=token).exists()


@csrf_exempt
@require_http_methods(["POST"])
def add_test_run(request, group_slug, project_slug, version, environment_slug):
    group = get_object_or_404(Group, slug=group_slug)
    project = get_object_or_404(group.projects, slug=project_slug)

    # authenticate token X project
    token = request.META.get('HTTP_AUTH_TOKEN', None)
    if token:
        if valid_token(token, project):
            pass
        else:
            return HttpResponseForbidden()
    else:
        return HttpResponse('Authentication needed', status=401)

    test_run_data = {
        'version': version,
        'environment_slug': environment_slug,
    }

    # TODO accept metadata

    if 'tests' in request.FILES:
        data = bytes()
        f = request.FILES['tests']
        for chunk in f.chunks():
            data = data + chunk
        test_run_data['tests_file'] = data.decode('utf-8')
    if 'metrics' in request.FILES:
        data = bytes()
        f = request.FILES['metrics']
        for chunk in f.chunks():
            data = data + chunk
        test_run_data['metrics_file'] = data.decode('utf-8')
    if 'log' in request.FILES:
        data = bytes()
        f = request.FILES['log']
        for chunk in f.chunks():
            data = data + chunk
        test_run_data['log_file'] = data.decode('utf-8')

    receive = ReceiveTestRun(project)
    receive(**test_run_data)

    return HttpResponse('', status=201)
