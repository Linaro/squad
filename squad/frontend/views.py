from collections import defaultdict
import json
import mimetypes
import os

from django.db.models import Count, Case, When, Q
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect

from squad.ci.models import TestJob
from squad.core.models import Group, Project, Metric, ProjectStatus, Status
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
    group = get_object_or_404(Group, slug=group_slug)
    context = {
        'group': group,
        'projects': group.projects.accessible_to(request.user),
    }
    return render(request, 'squad/group.html', context)


def __get_statuses__(project, limit=None):
    statuses = ProjectStatus.objects.filter(
        build__project=project
    ).prefetch_related(
        'build',
        'build__project'
    ).annotate(
        test_runs_total=Count('build__test_runs'),
        test_runs_completed=Count(Case(When(build__test_runs__completed=True, then=1))),
        test_runs_incomplete=Count(Case(When(build__test_runs__completed=False, then=1))),
    ).order_by('-build__datetime')
    if limit:
        statuses = statuses[:limit]
    return statuses


@auth
def project(request, group_slug, project_slug):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)

    statuses = __get_statuses__(project, 11)
    last_status = statuses.first()
    last_build = last_status and last_status.build

    metadata = last_build and sorted(last_build.important_metadata.items()) or ()
    extra_metadata = last_build and sorted(last_build.non_important_metadata.items()) or ()
    context = {
        'project': project,
        'statuses': statuses,
        'last_build': last_build,
        'metadata': metadata,
        'extra_metadata': extra_metadata,
    }
    return render(request, 'squad/project.html', context)


@auth
def builds(request, group_slug, project_slug):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)

    statuses = __get_statuses__(project)

    context = {
        'project': project,
        'statuses': statuses,
    }
    return render(request, 'squad/builds.html', context)


@auth
def build(request, group_slug, project_slug, version):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = get_object_or_404(
        project.builds.prefetch_related('test_runs'),
        version=version,
    )

    statuses = Status.objects.filter(
        test_run__build=build,
        suite__isnull=False,
    ).prefetch_related(
        'test_run',
        'test_run__environment',
        'suite',
    ).order_by('-tests_fail')

    count_statuses_nofail = len([s for s in statuses if s.has_tests and s.tests_fail == 0])
    count_statuses_fail = len([s for s in statuses if s.has_tests and s.tests_fail > 0])

    context = {
        'project': project,
        'build': build,
        'statuses': statuses,
        'count_statuses_nofail': count_statuses_nofail,
        'count_statuses_fail': count_statuses_fail,
        'metadata': sorted(build.important_metadata.items()),
        'extra_metadata': sorted(build.non_important_metadata.items()),
    }
    return render(request, 'squad/build.html', context)


@auth
def test_run(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = get_object_or_404(project.builds, version=build_version)
    test_run = get_object_or_404(build.test_runs, job_id=job_id)

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
        'metadata': sorted(test_run.metadata.items()),
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
    test_run = get_object_or_404(build.test_runs, job_id=job_id)

    if not test_run.log_file:
        raise Http404("No log file available for this test run")

    return HttpResponse(test_run.log_file, content_type="text/plain")


@auth
def test_run_tests(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = get_object_or_404(build.test_runs, job_id=job_id)

    filename = '%s_%s_%s_%s_tests.json' % (group.slug, project.slug, build.version, test_run.job_id)
    return __download__(filename, test_run.tests_file)


@auth
def test_run_metrics(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = get_object_or_404(build.test_runs, job_id=job_id)

    filename = '%s_%s_%s_%s_metrics.json' % (group.slug, project.slug, build.version, test_run.job_id)
    return __download__(filename, test_run.metrics_file)


@auth
def test_run_metadata(request, group_slug, project_slug, build_version, job_id):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = get_object_or_404(build.test_runs, job_id=job_id)

    filename = '%s_%s_%s_%s_metadata.json' % (group.slug, project.slug, build.version, test_run.job_id)
    return __download__(filename, test_run.metadata_file)


@auth
def attachment(request, group_slug, project_slug, build_version, job_id, fname):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.get(version=build_version)
    test_run = get_object_or_404(build.test_runs, job_id=job_id)

    attachment = get_object_or_404(test_run.attachments, filename=fname)
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


def test_job(request, testjob_id):
    testjob = get_object_or_404(TestJob, pk=testjob_id)
    if testjob.url is not None:
        # redirect to target executor
        return redirect(testjob.url)
    else:
        # display some description page
        context = {
            'testjob_id': testjob_id
        }
        return render(request, 'squad/testjob.html', context)
