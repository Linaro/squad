from collections import defaultdict
import json
import mimetypes
import os

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from squad.settings import PUBLIC_SITE
from squad.core.models import Group, Project, Metric
from squad.core.queries import get_metric_data
from squad.core.utils import join_name
from squad.frontend.utils import file_type


def login_required_on_private_site(func):
    if PUBLIC_SITE:
        return func
    else:
        return login_required(func)


@login_required_on_private_site
def home(request):
    context = {
        'projects': Project.objects.all(),
    }
    return render(request, 'squad/index.html', context)


@login_required_on_private_site
def group(request, group_slug):
    group = Group.objects.get(slug=group_slug)
    context = {
        'group': group,
        'projects': group.projects.all(),
    }
    return render(request, 'squad/group.html', context)


@login_required_on_private_site
def project(request, group_slug, project_slug):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    context = {
        'project': project,
    }
    return render(request, 'squad/project.html', context)


@login_required_on_private_site
def builds(request, group_slug, project_slug):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    builds = project.builds.prefetch_related('test_runs').order_by('-datetime').all()
    context = {
        'project': project,
        'builds': builds,
    }
    return render(request, 'squad/builds.html', context)


@login_required_on_private_site
def build(request, group_slug, project_slug, version):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.prefetch_related('test_runs', 'test_runs__status', 'test_runs__status__suite', 'test_runs__status__test_run__environment').get(version=version)
    context = {
        'project': project,
        'build': build,
    }
    return render(request, 'squad/build.html', context)


@login_required_on_private_site
def test_run(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = build.test_runs.get(job_id=job_id)

    metrics_by_suite = defaultdict(list)
    for metric in test_run.metrics.all():
        metrics_by_suite[metric.suite.slug].append(metric)

    tests_by_suite = defaultdict(list)
    for test in test_run.tests.all():
        tests_by_suite[test.suite.slug].append(test)

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
        'metrics_by_suite': metrics_by_suite.items(),
        'tests_by_suite': tests_by_suite.items(),
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


@login_required_on_private_site
def test_run_log(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = build.test_runs.get(job_id=job_id)

    filename = '%s_%s_%s_%s.log' % (group.slug, project.slug, build.version, test_run.job_id)
    return __download__(filename, test_run.log_file, 'text/plain')


@login_required_on_private_site
def test_run_tests(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = build.test_runs.get(job_id=job_id)

    filename = '%s_%s_%s_%s_tests.json' % (group.slug, project.slug, build.version, test_run.job_id)
    return __download__(filename, test_run.tests_file)


@login_required_on_private_site
def test_run_metrics(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = build.test_runs.get(job_id=job_id)

    filename = '%s_%s_%s_%s_metrics.json' % (group.slug, project.slug, build.version, test_run.job_id)
    return __download__(filename, test_run.metrics_file)


@login_required_on_private_site
def test_run_metadata(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = build.test_runs.get(job_id=job_id)

    filename = '%s_%s_%s_%s_metadata.json' % (group.slug, project.slug, build.version, test_run.job_id)
    return __download__(filename, test_run.metadata_file)


@login_required_on_private_site
def attachment(request, group_slug, project_slug, build_version, job_id, fname):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = build.test_runs.get(job_id=job_id)

    attachment = test_run.attachments.get(filename=fname)
    return __download__(attachment.filename, attachment.data)


@login_required_on_private_site
def charts(request, group_slug, project_slug):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)

    environments = [{"name": e.slug} for e in project.environments.order_by('id').all()]

    metric_set = Metric.objects.filter(
        test_run__environment__project=project
    ).values('suite__slug', 'name').order_by('suite__slug', 'name').distinct()
    metrics = [{"name": join_name(m['suite__slug'], m['name'])} for m in metric_set]

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
    return render(request, 'squad/charts.html', context)
