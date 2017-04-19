from django.http import HttpResponse
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
    backend = Backend.objects.get(name=request.POST.get('backend'))
    project = Project.objects.get(slug=project_slug, group__slug=group_slug)

    # definition can be received as a file upload or as a POST parameter
    if 'definition' in request.FILES:
        definition = read_file_upload(request.FILES['definition'])
    else:
        definition = request.POST.get('definition')

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

    return HttpResponse('', status=201)
