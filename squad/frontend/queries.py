from django.utils.translation import ugettext as _
from squad.core.models import Metric
from squad.core.utils import join_name


def get_metrics_list(project):

    metric_set = Metric.objects.filter(
        test_run__environment__project=project
    ).values('suite__slug', 'name').order_by('suite__slug', 'name').distinct()

    metrics = [{"name": ":tests:", "label": _("Test pass %"), "max": 100, "min": 0}]
    metrics += [{"name": join_name(m['suite__slug'], m['name'])} for m in metric_set]
    return metrics
