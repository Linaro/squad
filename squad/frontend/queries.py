from django.utils.translation import ugettext as _
from squad.core.models import Metric
from squad.core.utils import join_name


def get_metrics_list(project):
    unique_names = set()

    metric_set = Metric.objects.filter(environment__project=project).values('suite__slug', 'metadata__name')
    for m in metric_set:
        unique_names.add(join_name(m['suite__slug'], m['metadata__name']))

    metric_names = [{"name": name} for name in sorted(unique_names)]

    metrics = [{"name": ":summary:", "label": _("Summary of all metrics per build")}]
    metrics += [{"name": ":dynamic_summary:", "label": _("Summary of selected metrics"), "dynamic": "yes"}]
    metrics += [{"name": ":tests:", "label": _("Test pass %"), "max": 100, "min": 0}]
    metrics += metric_names
    return metrics
