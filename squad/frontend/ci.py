from django.shortcuts import render

from squad.http import auth
from squad.core.models import Group
from squad.ci.models import TestJob


@auth
def testjobs(request, group_slug, project_slug, build_version):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = project.builds.filter(version=build_version).last()

    testjobs = TestJob.objects.filter(
        target=project,
        build=build.version
    )

    context = {
        "project": project,
        "build": build,
        "testjobs": testjobs,
    }

    return render(request, 'squad/testjobs.html', context)
