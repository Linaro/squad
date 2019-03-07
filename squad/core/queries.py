import datetime

from squad.core import models
from django.db.models import Q, F, Sum
from django.utils import timezone


def get_metric_data(project, metrics, environments, date_start=None,
                    date_end=None):
    # Note that date_start and date_end **must** be datetime objects and not
    # strings, if used.

    date_start = timezone.make_aware(
        date_start or datetime.datetime.fromtimestamp(0))
    date_end = timezone.make_aware(date_end or datetime.datetime.now())

    results = {}
    for metric in metrics:
        if metric == ':tests:':
            results[metric] = get_tests_series(project, environments,
                                               date_start, date_end)
        else:
            results[metric] = get_metric_series(project, metric, environments,
                                                date_start, date_end)

    return results


def get_metric_series(project, metric, environments, date_start, date_end):
    entry = {}
    for environment in environments:
        series = models.Metric.objects.by_full_name(metric).filter(
            test_run__build__project=project,
            test_run__environment__slug=environment,
            test_run__created_at__range=(date_start, date_end)
        ).order_by(
            'test_run__datetime',
        ).values(
            'id',
            'test_run__build__datetime',
            'test_run__build__version',
            'result',
            'test_run__build__annotation__description',
            'is_outlier'
        )
        entry[environment] = [
            [int(p['test_run__build__datetime'].timestamp()), p['result'], p['test_run__build__version'], p['test_run__build__annotation__description'] or "", p['id'], str(p['is_outlier'])] for p in series
        ]
    return entry


def get_tests_series(project, environments, date_start, date_end):
    results = {}
    tests_total = (F('tests_pass') + F('tests_skip') + F('tests_fail') + F('tests_xfail'))
    for environment in environments:
        series = models.Status.objects.filter(
            test_run__build__project=project,
            suite=None,
            test_run__environment__slug=environment,
            test_run__created_at__range=(date_start, date_end)
        ).filter(
            Q(tests_pass__gt=0) | Q(tests_skip__gt=0) | Q(tests_fail__gt=0) | Q(tests_xfail__gt=0)
        ).order_by(
            'test_run__datetime'
        ).values(
            'test_run__build_id',
            'test_run__build__datetime',
            'test_run__build__version',
            'test_run__build__annotation__description',
        ).annotate(
            pass_percentage=100 * Sum('tests_pass') / Sum(tests_total)
        ).order_by('test_run__build__datetime')

        results[environment] = [
            [int(s['test_run__build__datetime'].timestamp()), s['pass_percentage'], s['test_run__build__version'], s['test_run__build__annotation__description'] or ""]
            for s in series
        ]
    return results
