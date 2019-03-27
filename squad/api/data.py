import json

from datetime import datetime

from django.http import HttpResponse
from django.http import HttpResponseBadRequest


from squad.core import models
from squad.core.queries import get_metric_data
from squad.core.utils import join_name
from squad.http import auth


def export_csv(results):
    lines = []
    for metric, data in results.items():
        for environment, entries in data.items():
            for entry in entries:
                line = [metric, environment] + entry
                lines.append(",".join(['"' + str(f) + '"' for f in line]))
    return "\n".join(lines)


@auth
def get(request, group_slug, project_slug):
    project = request.project

    metrics = request.GET.getlist('metric')
    date_start = request.GET.get('date_start', None)
    date_end = request.GET.get('date_end', None)

    if date_start:
        try:
            date_start = datetime.strptime(date_start, "%m-%d-%Y")
        except ValueError:
            return HttpResponseBadRequest("Invalid date_start format: %s. Try using %s notation." % (date_start, "%m-%d-%Y"))
    if date_end:
        try:
            date_end = datetime.strptime(date_end, "%m-%d-%Y")
        except ValueError:
            return HttpResponseBadRequest(
                "Invalid date_end format: %s. Try using %s notation." % (date_end, "%m-%d-%Y"))

    # If the metrics parameter is not present, return data for all metrics.
    if not metrics:
        metric_set = models.Metric.objects.filter(
            test_run__environment__project=project
        ).values('suite__slug', 'name').order_by('suite__slug', 'name').distinct()

        metrics = [":tests:"]
        metrics += [join_name(m['suite__slug'], m['name']) for m in metric_set]

    environments = request.GET.getlist('environment')

    results = get_metric_data(project, metrics, environments,
                              date_start, date_end)

    fmt = request.GET.get('format', 'json')
    if fmt == 'json':
        return HttpResponse(
            json.dumps(results),
            content_type='application/json; charset=utf-8'
        )
    elif fmt == 'csv':
        return HttpResponse(
            export_csv(results),
            content_type='test/csv; charset=utf-8'
        )
    else:
        return HttpResponseBadRequest("Invalid format: %s" % fmt)
