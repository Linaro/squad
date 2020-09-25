from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from squad.http import auth_privileged, read_file_upload, auth_user_from_request
from squad.ci.exceptions import SubmissionIssue
from squad.ci.tasks import submit
from squad.ci.models import Backend, TestJob
from squad.core.utils import log_addition


@require_http_methods(["POST"])
@csrf_exempt
@auth_privileged
def submit_job(request, group_slug, project_slug, version, environment_slug):
    backend_name = request.POST.get('backend')
    if backend_name is None:
        return HttpResponseBadRequest("backend field is required")

    try:
        backend = Backend.objects.get(name=backend_name)
    except Backend.DoesNotExist:
        return HttpResponseBadRequest("requested backend does not exist")

    # project has to exist or request will result with 404
    project = request.project
    if project is None:
        return HttpResponseBadRequest("malformed request")

    # create Build object
    build, _ = project.builds.get_or_create(version=version)

    # definition can be received as a file upload or as a POST parameter
    definition = None
    if 'definition' in request.FILES:
        definition = read_file_upload(request.FILES['definition']).decode('utf-8')
    else:
        definition = request.POST.get('definition')

    if definition is None:
        return HttpResponseBadRequest("test job definition is required")

    # create TestJob object
    test_job = TestJob.objects.create(
        backend=backend,
        definition=definition,
        target=project,
        target_build=build,
        environment=environment_slug,
    )
    log_addition(request, test_job, "Test Job submission")
    # schedule submission
    submit.delay(test_job.id)

    # return ID of test job
    return HttpResponse(test_job.id, status=201)


@require_http_methods(["POST"])
@csrf_exempt
@auth_privileged
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
    project = request.project
    if backend is None or project is None:
        return HttpResponseBadRequest("malformed request")

    # create Build object
    build, _ = project.builds.get_or_create(version=version)

    # testjob_id points to the backend's test job
    testjob_id = request.POST.get('testjob_id', None)

    if testjob_id is None:
        return HttpResponseBadRequest("testjob_id is required")

    # create TestJob object
    test_job = TestJob.objects.create(
        backend=backend,
        target=project,
        target_build=build,
        environment=environment_slug,
        submitted=True,
        job_id=testjob_id
    )
    log_addition(request, test_job, "Watch Job submission")

    # return ID of test job
    return HttpResponse(test_job.id, status=201)


@require_http_methods(["POST"])
@csrf_exempt
def resubmit_job(request, test_job_id, method='resubmit'):
    testjob = get_object_or_404(TestJob.objects, pk=test_job_id)
    user = auth_user_from_request(request, request.user)
    project = testjob.target
    if not project.can_submit_testjobs(user):
        return HttpResponse(status=401)

    call = getattr(testjob, method)
    try:
        ret_value = call()
        new_testjob = testjob.resubmitted_jobs.last()
        if new_testjob is not None:
            log_addition(request, new_testjob, "Create testjob as resubmission")
    except SubmissionIssue as e:
        return HttpResponse(str(e), status=500)

    if ret_value:
        return HttpResponse(status=201)
    # return 403 when resubmit call is unsuccessful
    return HttpResponse(status=403)


@require_http_methods(["POST"])
@csrf_exempt
def force_resubmit_job(request, test_job_id):
    return resubmit_job(request, test_job_id, method='force_resubmit')
