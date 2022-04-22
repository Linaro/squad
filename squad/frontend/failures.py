from django.core.paginator import InvalidPage, Paginator
from django.http import Http404
from django.shortcuts import render

from squad.core.failures import failures_with_confidence
from squad.http import auth
from squad.frontend.views import get_build


@auth
def failures(request, group_slug, project_slug, build_version):
    project = request.project
    build = get_build(project, build_version)
    environments = project.environments.order_by("slug")

    failures = build.tests.filter(
        result=False,
    ).exclude(
        has_known_issues=True,
    ).only(
        'suite__slug', 'metadata__name', 'metadata__id',
    ).order_by(
        'suite__slug', 'metadata__name',
    ).distinct().values_list(
        'suite__slug', 'metadata__name', 'metadata__id', named=True,
    )

    search = request.GET.get('search', '')
    if search:
        failures = failures.filter(metadata__name__icontains=search)

    try:
        page_num = request.GET.get('page', 1)
        paginator = Paginator(failures, 25)
        page = paginator.page(page_num)
    except InvalidPage as ip:
        raise Http404(('Invalid page (%(page_number)s): %(message)s') % {
            'page_number': page_num,
            'message': str(ip),
        })

    fwc = failures_with_confidence(project, build, page)
    rows = {}
    for t in fwc:
        if t.environment.slug not in rows:
            rows[t.environment.slug] = {}

        rows[t.environment.slug][t.full_name] = t

    context = {
        "project": project,
        "build": build,
        "environments": environments,
        "page": page,
        "rows": rows,
        "search": search,
    }

    return render(request, 'squad/failures.jinja2', context)
