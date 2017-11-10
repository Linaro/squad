from squad.core import models
from django.db.models import Q, F, Value


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
    tests_total = (F('tests_pass') + F('tests_skip') + F('tests_fail'))
    pass_percentage = Value('100') * F('tests_pass') / tests_total
    for environment in environments:
        series = models.ProjectStatus.objects.filter(
            build__project=project
        ).filter(
            Q(tests_pass__gt=0) | Q(tests_skip__gt=0) | Q(tests_fail__gt=0)
        ).order_by(
            'build__datetime'
        ).values(
            'build__datetime',
            'build__version',
        ).annotate(
            pass_percentage=pass_percentage
        )
        results[environment] = [
            [int(s['build__datetime'].timestamp()), s['pass_percentage'], s['build__version']]
            for s in series
        ]
    return results
