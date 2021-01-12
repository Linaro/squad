from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import json
import logging


from squad.http import read_file_upload
from squad.http import auth_submit_results

from squad.core.callback import create_callback
from squad.core.models import Build
from squad.core.models import PatchSource


from squad.core.tasks import CreateBuild
from squad.core.tasks import ReceiveTestRun
from squad.core.tasks import exceptions


from squad.core.utils import log_addition
from squad.core.utils import log_change


from squad.version import __version__


logger = logging.getLogger()


@csrf_exempt
@require_http_methods(["POST"])
@auth_submit_results
def create_build(request, group_slug, project_slug, version):
    project = request.project

    fields = {}
    patch_source = request.POST.get('patch_source', None)
    try:
        if patch_source:
            fields['patch_source'] = PatchSource.objects.get(name=patch_source)
    except PatchSource.DoesNotExist:
        return HttpResponse('Unknown patch source: %s' % patch_source, status=400)

    patch_baseline = request.POST.get('patch_baseline', None)
    try:
        if patch_baseline:
            fields['patch_baseline'] = project.builds.get(version=patch_baseline)
    except Build.DoesNotExist:
        return HttpResponse('Unknown patch baseline: %s' % patch_baseline, status=400)

    patch_id = request.POST.get('patch_id', None)
    if patch_id:
        fields['patch_id'] = patch_id

    create_build = CreateBuild(project)
    new_build, created = create_build(version=version, **fields)
    if created:
        log_addition(request, new_build, "Build created")
    else:
        log_change(request, new_build, "Build updated")

    try:
        create_callback(new_build, request)
    except (ValidationError, IntegrityError) as e:
        return HttpResponse(', '.join(e.messages), status=400)

    return HttpResponse('', status=201)


@csrf_exempt
@require_http_methods(["POST"])
@auth_submit_results
def add_test_run(request, group_slug, project_slug, version, environment_slug):
    project = request.project

    test_run_data = {
        'version': version,
        'environment_slug': environment_slug,
    }

    uploads = {
        'tests_file': 'tests',
        'metrics_file': 'metrics',
        'log_file': 'log',
        'metadata_file': 'metadata',
    }
    for key, field in uploads.items():
        if field in request.FILES:
            f = request.FILES[field]
            test_run_data[key] = read_file_upload(f).decode('utf-8')
        elif field in request.POST:
            test_run_data[key] = request.POST[field]

    if 'metadata_file' not in test_run_data:
        metadata = {}
        for field in ReceiveTestRun.SPECIAL_METADATA_FIELDS:
            if field in request.POST:
                metadata[field] = request.POST[field]
        if metadata:
            test_run_data['metadata_file'] = json.dumps(metadata)

    if 'attachment' in request.FILES:
        attachments = {}
        for f in request.FILES.getlist('attachment'):
            attachments[f.name] = read_file_upload(f)
        test_run_data['attachments'] = attachments

    receive = ReceiveTestRun(project)

    try:
        testrun, build = receive(**test_run_data)
        log_addition(request, testrun, "Test Run created")
        if build:
            log_addition(request, build, "Build created")
    except (exceptions.invalid_input + (exceptions.DuplicatedTestJob,)) as e:
        logger.warning(request.get_full_path() + ": " + str(e))
        return HttpResponse(str(e), status=400)

    return HttpResponse('', status=201)


@csrf_exempt
def version(request):
    return HttpResponse(__version__)
