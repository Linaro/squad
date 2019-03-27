from django.shortcuts import render
from django.http import Http404

from squad.http import auth
from squad.ci.models import TestJob


@auth
def testjobs(request, group_slug, project_slug, build_version):
    project = request.project
    build = project.builds.filter(version=build_version).last()

    if build is None:
        raise Http404()
    testjobs = TestJob.objects.filter(
        target=project,
        target_build=build
    )

    context = {
        "project": project,
        "build": build,
        "testjobs": testjobs,
    }

    return render(request, 'squad/testjobs.jinja2', context)
