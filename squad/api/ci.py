from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


from squad.http import auth, read_file_upload
from squad.ci import models
from squad.ci.tasks import submit
from squad.ci.models import Backend, TestJob
from squad.core.models import Project


@require_http_methods(["POST"])
@csrf_exempt
@auth
def submit_job(request, group_slug, project_slug, version, environment_slug):
    backend_name = request.POST.get('backend')
    if backend_name is None:
        return HttpResponseBadRequest("backend field is required")
    backend = None
    try:
        backend = Backend.objects.get(name=request.POST.get('backend'))
    except Backend.DoesNotExist:
        return HttpResponseBadRequest("requested backend does not exist")

    # project has to exist or request will result with 404
    project = Project.objects.get(slug=project_slug, group__slug=group_slug)
    if backend is None or project is None:
        return HttpResponseBadRequest("malformed request")

    # definition can be received as a file upload or as a POST parameter
    definition = None
    if 'definition' in request.FILES:
        definition = read_file_upload(request.FILES['definition'])
    else:
        definition = request.POST.get('definition')

    if definition is None:
        return HttpResponseBadRequest("test job definition is required")

    # create TestJob object
    test_job = TestJob.objects.create(
        backend=backend,
        definition=definition,
        target=project,
        build=version,
        environment=environment_slug,
    )
    # schedule submission
    submit.delay(test_job.id)

    # return ID of test job
    return HttpResponse(test_job.id, status=201)


@require_http_methods(["POST"])
@csrf_exempt
@auth
def watch_job(request, group_slug, project_slug, version, environment_slug):
    backend_name = request.POST.get('backend')
    if backend_name is None:
        return HttpResponseBadRequest("backend field is required")
    backend = None
    try:
        backend = Backend.objects.get(name=request.POST.get('backend'))
    except Backend.DoesNotExist:
        return HttpResponseBadRequest("requested backend does not exist")

    # project has to exist or request will result with 400
    project = Project.objects.get(slug=project_slug, group__slug=group_slug)
    if backend is None or project is None:
        return HttpResponseBadRequest("malformed request")

    # testjob_id points to the backend's test job
    testjob_id = request.POST.get('testjob_id', None)

    if testjob_id is None:
        return HttpResponseBadRequest("testjob_id is required")

    # create TestJob object
    test_job = TestJob.objects.create(
        backend=backend,
        target=project,
        build=version,
        environment=environment_slug,
        job_id=testjob_id
    )

    # return ID of test job
    return HttpResponse(test_job.id, status=201)
