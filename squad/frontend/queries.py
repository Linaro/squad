from django.utils.translation import ugettext as _
from squad.core.models import Metric, TestRun
from squad.core.utils import join_name, split_list


def get_metrics_list(project):
    unique_names = set()

    testruns = TestRun.objects.filter(environment__project=project).values('id').order_by('id')
    test_runs_ids = [tr['id'] for tr in testruns]
    for chunk in split_list(test_runs_ids, chunk_size=100):
        metric_set = Metric.objects.filter(test_run_id__in=chunk).values('suite__slug', 'name')
        for m in metric_set:
            unique_names.add(join_name(m['suite__slug'], m['name']))

    metric_names = [{"name": name} for name in sorted(unique_names)]

    metrics = [{"name": ":summary:", "label": _("Summary of all metrics per build")}]
    metrics += [{"name": ":dynamic_summary:", "label": _("Summary of selected metrics"), "dynamic": "yes"}]
    metrics += [{"name": ":tests:", "label": _("Test pass %"), "max": 100, "min": 0}]
    metrics += metric_names
    return metrics
