from django.shortcuts import render

from squad.http import auth
from squad.frontend.views import get_build


@auth
def failures(request, group_slug, project_slug, build_version):
    project = request.project
    build = get_build(project, build_version)
    failures = build.failures
    environments = project.environments.order_by("slug")

    search = request.GET.get('search', '')

    if search:
        failures = failures.filter(metadata__name__icontains=search)

    unique_failures = sorted(set([t.full_name for t in failures]))

    rows = {}
    for t in build.failures:
        if t.environment.slug not in rows:
            rows[t.environment.slug] = {}

        rows[t.environment.slug][t.full_name] = t

    context = {
        "project": project,
        "build": build,
        "environments": environments,
        "ufailures": unique_failures,
        "rows": rows,
        "search": search,
    }

    return render(request, 'squad/failures.jinja2', context)
