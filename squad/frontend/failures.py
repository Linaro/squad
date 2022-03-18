from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import Http404
from django.shortcuts import render

from squad.http import auth
from squad.frontend.views import get_build


@auth
def failures(request, group_slug, project_slug, build_version):
    project = request.project
    build = get_build(project, build_version)
    environments = project.environments.order_by("slug")

    all_failures = build.failures

    search = request.GET.get('search', '')
    if search:
        all_failures = all_failures.filter(metadata__name__icontains=search)

    page = request.GET.get('page', 1)
    unique_failures = sorted(set([t.full_name for t in all_failures]))
    paginator = Paginator(unique_failures, 25)

    try:
        failures = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        raise Http404()

    rows = {}
    for t in all_failures:
        if t.environment.slug not in rows:
            rows[t.environment.slug] = {}

        rows[t.environment.slug][t.full_name] = t

    context = {
        "project": project,
        "build": build,
        "environments": environments,
        "failures": failures,
        "rows": rows,
        "search": search,
    }

    return render(request, 'squad/failures.jinja2', context)
