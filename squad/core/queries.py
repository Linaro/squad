from squad.core import models


def get_metric_data(project, metrics, environments):
    results = {}
    for metric in metrics:
        entry = {}
        for environment in environments:
            series = models.Metric.objects.by_full_name(metric).filter(
                test_run__build__project=project,
                test_run__environment__slug=environment,
            ).order_by(
                'test_run__datetime',
            ).values(
                'test_run__datetime',
                'test_run__build__version',
                'result',
            )
            entry[environment] = [
                [int(p['test_run__datetime'].timestamp()), p['result'], p['test_run__build__version']] for p in series
            ]
        results[metric] = entry

    return results
