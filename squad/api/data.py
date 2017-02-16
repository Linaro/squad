import json
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.http import HttpResponseForbidden


from squad.core import models
from squad.core.queries import get_metric_data
from squad.http import auth


@auth
def get(request, group_slug, project_slug):
    group = get_object_or_404(models.Group, slug=group_slug)
    project = get_object_or_404(group.projects, slug=project_slug)

    metrics = request.GET.getlist('metric')
    environments = request.GET.getlist('environment')

    results = get_metric_data(project, metrics, environments)

    return HttpResponse(
        json.dumps(results),
        content_type='application/json; charset=utf-8'
    )
