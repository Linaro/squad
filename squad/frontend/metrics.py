from django.shortcuts import render

from squad.http import auth
from squad.core.models import Environment, Metric
from squad.frontend.views import get_build


@auth
def build_metrics(request, group_slug, project_slug, build_version):
    project = request.project
    build = get_build(project, build_version)
    environments = Environment.objects.filter(project=project).order_by("name")
    metrics = Metric.objects.filter(build=build).prefetch_related("metadata", "environment")

    search = request.GET.get('search', '')

    visited = set()
    umetrics = [visited.add(m.full_name) or m for m in metrics if m.full_name not in visited]
    umetrics.sort(key=lambda um: um.full_name)

    rows = {}
    for m in metrics:
        if m.environment.slug not in rows:
            rows[m.environment.slug] = {}

        rows[m.environment.slug][m.full_name] = m

    context = {
        "project": project,
        "build": build,
        "environments": environments,
        "metrics": metrics,
        "umetrics": umetrics,
        "rows": rows,
        "search": search,
    }

    return render(request, 'squad/build_metrics.jinja2', context)
