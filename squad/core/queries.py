import datetime
from collections import Counter
from itertools import groupby
from functools import reduce

from squad.core import models
from squad.core.statistics import geomean
from squad.core.utils import parse_name
from django.core.exceptions import ObjectDoesNotExist
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
        elif metric == ':summary:':
            results[metric] = get_summary_series(project, environments,
                                                 date_start, date_end)
        elif metric == ':dynamic_summary:':
            real_metrics = [m for m in metrics if m not in [':tests:', ':summary:', ':dynamic_summary:']]
            results[metric] = get_dynamic_summary(project, environments,
                                                  real_metrics, date_start,
                                                  date_end)
        else:
            results[metric] = get_metric_series(project, metric, environments,
                                                date_start, date_end)

    return results


def split_measurements(liststr):
    return sorted([float(f) for f in liststr.split(',')])


def get_min(liststr):
    return split_measurements(liststr)[0]


def get_max(liststr):
    return split_measurements(liststr)[-1]


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
            'is_outlier',
            'measurements',
        )
        entry[environment] = [
            [
                int(p['test_run__build__datetime'].timestamp()),
                p['result'],
                p['test_run__build__version'],
                p['test_run__build__annotation__description'] or "",
                p['id'],
                str(p['is_outlier']),
                get_min(p['measurements']),
                get_max(p['measurements']),
            ] for p in series
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
            [
                int(s['test_run__build__datetime'].timestamp()),
                s['pass_percentage'],
                s['test_run__build__version'],
                s['test_run__build__annotation__description'] or "",
            ]
            for s in series
        ]
    return results


def get_summary_series(project, environments, date_start, date_end):
    results = {}
    for environment in environments:
        series = models.BuildSummary.objects.filter(
            build__project=project,
            environment__slug=environment,
            build__created_at__range=(date_start, date_end)
        ).filter(
            metrics_summary__gt=0
        ).order_by(
            'datetime'
        ).values(
            'metrics_summary',
            'build_id',
            'build__datetime',
            'build__version',
            'build__annotation__description',
        ).order_by('build__datetime')

        results[environment] = [
            [
                int(s['build__datetime'].timestamp()),
                s['metrics_summary'],
                s['build__version'],
                s['build__annotation__description'] or "",
            ]
            for s in series
        ]
    return results


def get_dynamic_summary(project, environments, metrics, date_start, date_end):
    entry = {}
    filters = []
    if not metrics:
        for env in environments:
            entry[env] = []
        return entry
    for m in metrics:
        suite, metric = parse_name(m)
        filters.append(Q(suite__slug=suite) & Q(name=metric))
    metric_filter = reduce(lambda x, y: x | y, filters)

    data = models.Metric.objects.filter(
        test_run__build__project=project,
        test_run__environment__slug__in=environments,
        test_run__created_at__range=(date_start, date_end),
    ).filter(
        metric_filter
    ).prefetch_related(
        'test_run',
        'test_run__environment',
        'test_run__build',
        'test_run__build__annotation',
    ).order_by('test_run__environment__id', 'test_run__build__id')

    for environment, metrics_by_environment in groupby(data, lambda m: m.test_run.environment):
        envdata = []
        metrics_by_build = groupby(metrics_by_environment, lambda m: m.test_run.build)
        for build, metric_list in metrics_by_build:
            values = []
            for metric in metric_list:
                if not metric.is_outlier:
                    values = values + metric.measurement_list
            try:
                description = build.annotation.description
            except ObjectDoesNotExist:
                description = ""
            envdata.append([
                build.datetime.timestamp(),
                geomean(values),
                build.version,
                description,
            ])
        entry[environment.slug] = sorted(envdata, key=(lambda e: e[0]))

    return entry


def test_confidence(test, list_of_duplicates=None):
    status_priority = ['fail', 'pass', 'xfail', 'skip']

    def most_common(lst):
        data = Counter(lst)
        max_count = max(data.values())
        return {value: count for value, count in data.items() if count == max_count}

    if test:
        duplicates = models.Test.objects.filter(suite=test.suite, metadata=test.metadata, environment_id=test.environment_id, build_id=test.build_id).order_by()
    else:
        duplicates = list_of_duplicates

    if len(duplicates) == 1:
        return test.status, None
    else:
        most_frequent_statuses = most_common(
            [t.status for t in duplicates])
        if not len(most_frequent_statuses) == 1:
            for s in status_priority:
                # Get the most prioritized status based on priority list.
                if s in most_frequent_statuses.keys():
                    return_status = s
                    break
        else:
            return_status = list(most_frequent_statuses.keys())[0]

        confidence_score = list(most_frequent_statuses.values())[0] / len(duplicates) * 100
        return [return_status, confidence_score]
