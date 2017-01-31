from squad.core import models


def get_metric_data(project, metrics, environments):
    results = {}
    for metric in metrics:
        if metric == ':tests:':
            results[metric] = get_tests_series(project, environments)
        else:
            results[metric] = get_metric_series(project, metric, environments)

    return results


def get_metric_series(project, metric, environments):
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
    return entry


def get_tests_series(project, environments):
    results = {}
    for environment in environments:
        series = models.Status.objects.overall().filter(
            test_run__build__project=project,
            test_run__environment__slug=environment,
        ).order_by('test_run__datetime').prefetch_related('test_run', 'test_run__environment')
        results[environment] = [
            [s.test_run.datetime.timestamp(), s.pass_percentage]
            for s in series
        ]
    return results
