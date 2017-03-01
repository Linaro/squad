from collections import defaultdict
import json
import mimetypes
import os

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from squad.core.models import Group, Project, Metric
from squad.core.queries import get_metric_data
from squad.core.utils import join_name
from squad.frontend.utils import file_type
from squad.http import auth


def home(request):
    context = {
        'projects': Project.objects.accessible_to(request.user),
    }
    return render(request, 'squad/index.html', context)


def group(request, group_slug):
    group = Group.objects.get(slug=group_slug)
    context = {
        'group': group,
        'projects': group.projects.accessible_to(request.user),
    }
    return render(request, 'squad/group.html', context)


@auth
def project(request, group_slug, project_slug):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    context = {
        'project': project,
    }
    return render(request, 'squad/project.html', context)


@auth
def builds(request, group_slug, project_slug):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    builds = project.builds.prefetch_related('test_runs').order_by('-datetime').all()
    context = {
        'project': project,
        'builds': builds,
    }
    return render(request, 'squad/builds.html', context)


@auth
def build(request, group_slug, project_slug, version):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.prefetch_related('test_runs', 'test_runs__status', 'test_runs__status__suite', 'test_runs__status__test_run__environment').get(version=version)
    context = {
        'project': project,
        'build': build,
    }
    return render(request, 'squad/build.html', context)


@auth
def test_run(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = build.test_runs.get(job_id=job_id)

    status = test_run.status.by_suite()

    tests_status = [s for s in status if s.has_tests]
    metrics_status = [s for s in status if s.has_metrics]

    attachments = [
        (f['filename'], file_type(f['filename']), f['length'])
        for f in test_run.attachments.values('filename', 'length')
    ]

    context = {
        'project': project,
        'build': build,
        'test_run': test_run,
        'metadata': json.loads(test_run.metadata_file or '{}'),
        'attachments': attachments,
        'tests_status': tests_status,
        'metrics_status': metrics_status,
    }
    return render(request, 'squad/test_run.html', context)


def __download__(filename, data, content_type=None):
    if not content_type:
        content_type, _ = mimetypes.guess_type(filename)
        if content_type is None:
            content_type = 'application/octet-stream'
    response = HttpResponse(data, content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


@auth
def test_run_log(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = build.test_runs.get(job_id=job_id)

    filename = '%s_%s_%s_%s.log' % (group.slug, project.slug, build.version, test_run.job_id)
    return __download__(filename, test_run.log_file, 'text/plain')


@auth
def test_run_tests(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = build.test_runs.get(job_id=job_id)

    filename = '%s_%s_%s_%s_tests.json' % (group.slug, project.slug, build.version, test_run.job_id)
    return __download__(filename, test_run.tests_file)


@auth
def test_run_metrics(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = build.test_runs.get(job_id=job_id)

    filename = '%s_%s_%s_%s_metrics.json' % (group.slug, project.slug, build.version, test_run.job_id)
    return __download__(filename, test_run.metrics_file)


@auth
def test_run_metadata(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = build.test_runs.get(job_id=job_id)

    filename = '%s_%s_%s_%s_metadata.json' % (group.slug, project.slug, build.version, test_run.job_id)
    return __download__(filename, test_run.metadata_file)


@auth
def attachment(request, group_slug, project_slug, build_version, job_id, fname):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = build.test_runs.get(job_id=job_id)

    attachment = test_run.attachments.get(filename=fname)
    return __download__(attachment.filename, attachment.data)


@auth
def metrics(request, group_slug, project_slug):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)

    environments = [{"name": e.slug} for e in project.environments.order_by('id').all()]

    metric_set = Metric.objects.filter(
        test_run__environment__project=project
    ).values('suite__slug', 'name').order_by('suite__slug', 'name').distinct()

    metrics = [{"name": ":tests:", "label": "Test pass %", "max": 100, "min": 0}]
    metrics += [{"name": join_name(m['suite__slug'], m['name'])} for m in metric_set]

    data = get_metric_data(
        project,
        request.GET.getlist('metric'),
        request.GET.getlist('environment')
    )

    context = {
        "project": project,
        "environments": environments,
        "metrics": metrics,
        "data": data,
    }
    return render(request, 'squad/metrics.html', context)
