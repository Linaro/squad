from django.shortcuts import render

from squad.core.failures import FailuresWithConfidence
from squad.http import auth
from squad.frontend.views import get_build


@auth
def failures(request, group_slug, project_slug, build_version):
    project = request.project
    build = get_build(project, build_version)
    environments = project.environments.order_by("slug")
    fc = FailuresWithConfidence(project, build)

    page = request.GET.get('page', 1)
    search = request.GET.get('search', '')

    fc = FailuresWithConfidence(project, build, page=int(page), search=search)

    rows = {}
    for t in fc.failures():
        if t.environment.slug not in rows:
            rows[t.environment.slug] = {}

        rows[t.environment.slug][t.full_name] = t

    context = {
        "project": project,
        "build": build,
        "environments": environments,
        "page": page,
        "fc": fc,
        "rows": rows,
        "search": search,
    }

    return render(request, 'squad/failures.jinja2', context)
