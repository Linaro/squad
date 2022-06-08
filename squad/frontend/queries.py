from django.utils.translation import gettext as _
from squad.core.models import Metric, SuiteMetadata
from squad.core.utils import join_name


def get_metrics_list(project):
    unique_names = set()

    envs_ids = project.environments.values_list('id', flat=True)
    metric_set = Metric.objects.filter(environment_id__in=list(envs_ids)).only('metadata_id').distinct().values_list('metadata_id', flat=True)
    names = SuiteMetadata.objects.filter(id__in=list(metric_set)).only('suite', 'name')
    for n in names:
        unique_names.add(join_name(n.suite, n.name))

    metric_names = [{"name": name} for name in sorted(unique_names)]

    metrics = [{"name": ":summary:", "label": _("Summary of all metrics per build")}]
    metrics += [{"name": ":dynamic_summary:", "label": _("Summary of selected metrics"), "dynamic": "yes"}]
    metrics += [{"name": ":tests:", "label": _("Test pass %"), "max": 100, "min": 0}]
    metrics += metric_names
    return metrics
