from django.core.paginator import Paginator, EmptyPage
from django.shortcuts import render
from django.http import Http404
from django.db.models import Prefetch

from squad.http import auth
from squad.ci.models import TestJob
from squad.core.models import TestRun


@auth
def testjobs(request, group_slug, project_slug, build_version):
    testjobs = TestJob.objects.prefetch_related(
        Prefetch('testrun', queryset=TestRun.objects.only('build', 'environment', 'job_id')),
        'testrun__build__project__group',
        'target__group',
        'target_build',
        'backend',
        'parent_job__backend')

    project = request.project
    build = project.builds.filter(version=build_version).prefetch_related(Prefetch('test_jobs', queryset=testjobs), 'annotation').last()
    if build is None:
        raise Http404()

    try:
        paginator = Paginator(build.test_jobs.all(), 25)
        page = request.GET.get('page', 1)
        testjobs_page = paginator.page(page)
        context = {
            "project": project,
            "build": build,
            "testjobs": testjobs_page,
        }

        return render(request, 'squad/testjobs.jinja2', context)
    except EmptyPage:
        raise Http404()
