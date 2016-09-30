from collections import defaultdict
import os

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from squad.core.models import Group, Project


PUBLIC_SITE = bool(os.getenv('SQUAD_PUBLIC_SITE'))


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
    pass


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
    return render(request, 'squad/project/builds.html', context)


@login_required_on_private_site
def build(request, group_slug, project_slug, version):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.prefetch_related('test_runs', 'test_runs__status', 'test_runs__status__suite', 'test_runs__status__test_run__environment').get(version=version)
    context = {
        'project': project,
        'build': build,
    }
    return render(request, 'squad/project/build.html', context)


def test_run(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = build.test_runs.get(job_id=job_id)

    metrics_by_suite = defaultdict(list)
    for metric in test_run.metrics.all():
        metrics_by_suite[metric.suite.slug].append(metric)

    context = {
        'project': project,
        'build': build,
        'test_run': test_run,
        'metrics_by_suite': metrics_by_suite.items(),
    }
    return render(request, 'squad/project/test_run.html', context)
