from collections import OrderedDict
from django.db.models import F
from itertools import groupby
from functools import reduce
import statistics


from squad.core.utils import parse_name, join_name
from squad.core import models


class BaseComparison(object):
    """
    Data structure:

    builds: [Build]
    environments: Build → [EnvironmentName(str)]
    results: Name(str) → ((Build,EnvironmentName(str)) → Results)

    The best way to think about this is to think of the table you want as
    result:

    +---------+---------------+---------------+
    |         |    build 1    |    build 2    |
    +         +-------+-------+-------+-------+
    |         | env 1 | env 2 | env 1 | env 2 |
    +---------+-------+-------+-------+-------+
    | result1 |       |       |       |       |
    | result2 |       |       |       |       |
    | result3 |       |       |       |       |
    | result4 |       |       |       |       |
    +---------+-------+-------+-------+-------+

    `builds` is the list of builds (the top header row)

    `environments` is a mapping between a build and the list of environments
    (the bottom header row)

    `results` contains the body of the table. It is a mapping between a test
    or metric name string (row) to the results for that row. results[name] is
    then a mapping, between Environment (the column) and the result (the cells
    in the table). So results[name][env] gives you the value of the cell at
    (name, env)
    """

    def __init__(self, *builds):
        self.builds = list(builds)
        self.environments = OrderedDict()
        self.all_environments = set()
        self.results = OrderedDict()

        for build in self.builds:
            self.environments[build] = set()

        self.__extract_results__()

    @classmethod
    def compare_builds(cls, *builds):
        builds = [b for b in builds if b]
        return cls(*builds)

    @classmethod
    def compare_projects(cls, *projects):
        builds = [p.builds.last() for p in projects]
        return cls.compare_builds(*builds)

    def __extract_results__(self):
        raise NotImplementedError

    __diff__ = None

    @property
    def diff(self):
        """
        Returns a subset of the rows, containing only the rows where results
        differ between the builds.
        """
        if self.__diff__ is not None:
            return self.__diff__

        d = OrderedDict()
        for item, results in self.results.items():
            previous = None
            for build in self.builds:
                current = [results.get((build, e)) for e in self.environments[build]]
                if previous and previous != current:
                    d[item] = results
                    break
                previous = current

        self.__diff__ = d
        return self.__diff__


class MetricComparison(BaseComparison):

    __builds_dict__ = None

    def __get_build__(self, build_id):
        if self.__builds_dict__ is None:
            self.__builds_dict__ = {b.id: b for b in self.builds}
        return self.__builds_dict__[build_id]

    def __extract_stats__(self, query):
        stats = []
        for environment_slug, builds in groupby(query, lambda x: x['test_run__environment__slug']):
            for build_id, suites in groupby(builds, lambda x: x['test_run__build_id']):
                for suite_slug, metrics in groupby(suites, lambda x: x['suite__slug']):
                    for metric_name, measurements in groupby(metrics, lambda x: x['name']):
                        values = []
                        for m in measurements:
                            values += [float(v) for v in m['measurements'].split(',')]
                        stat = {
                            'environment_slug': environment_slug,
                            'build_id': build_id,
                            'full_name': join_name(suite_slug, metric_name),
                            'mean': statistics.mean(values),
                            'stddev': statistics.pstdev(values),
                            'count': len(values)
                        }
                        stats.append(stat)
        return stats

    def __extract_results__(self):
        metrics = models.Metric.objects.filter(
            test_run__build__in=self.builds,
            is_outlier=False
        ).values(
            'test_run__environment__slug',
            'test_run__build_id',
            'suite__slug',
            'name',
            'measurements'
        ).order_by(
            'test_run__environment__slug',
            'test_run__build_id',
            'suite__slug',
            'name'
        )

        results = self.__extract_stats__(metrics)
        for result in results:
            environment = result['environment_slug']
            build = self.__get_build__(result['build_id'])
            full_name = result['full_name']
            mean = result['mean']
            stddev = result['stddev']
            count = result['count']

            self.all_environments.add(environment)
            self.environments[build].add(environment)
            key = (build, environment)

            if full_name not in self.results:
                self.results[full_name] = OrderedDict()
            self.results[full_name][key] = (mean, stddev, count)

        self.results = OrderedDict(sorted(self.results.items()))
        for build in self.builds:
            self.environments[build] = sorted(self.environments[build])


class TestComparison(BaseComparison):

    __test__ = False

    def __init__(self, *builds, regressions_and_fixes_only=False):
        self.__intermittent__ = {}
        self.regressions_and_fixes_only = regressions_and_fixes_only
        BaseComparison.__init__(self, *builds)

    def __extract_results__(self):
        if self.regressions_and_fixes_only:
            self.__regressions_and_fixes__(self.builds[0], self.builds[1])
            return

        test_runs = models.TestRun.objects.filter(
            build__in=self.builds,
        ).prefetch_related(
            'build',
            'environment',
        )
        for test_run in test_runs:
            build = test_run.build
            environment = test_run.environment
            self.all_environments.add(str(environment))
            self.environments[build].add(str(environment))
            self.__extract_test_results__(test_run)
        self.results = OrderedDict(sorted(self.results.items()))
        for build in self.builds:
            self.environments[build] = sorted(self.environments[build])

    def __extract_test_results__(self, test_run):
        tests = test_run.tests.annotate(
            suite_slug=F('suite__slug'),
        )
        for test in tests.iterator():
            key = (test_run.build, str(test_run.environment))
            full_name = join_name(test.suite_slug, test.name)
            if full_name not in self.results:
                self.results[full_name] = OrderedDict()
            self.results[full_name][key] = test.status
            if test.has_known_issues:
                for issue in test.known_issues.all():
                    if issue.intermittent:
                        env = str(test_run.environment)
                        self.__intermittent__[(full_name, env)] = True

    __regressions__ = None
    __fixes__ = None

    @property
    def regressions(self):
        if self.__regressions__ is None:
            self.__regressions__ = self.__status_changes__(('pass', 'fail'))
        return self.__regressions__

    @property
    def fixes(self):
        if self.__fixes__ is None:
            self.__fixes__ = self.__status_changes__(
                ('fail', 'pass'),
                ('xfail', 'pass'),
                predicate=lambda test, env: (test, env) not in self.__intermittent__
            )
        return self.__fixes__

    def apply_transitions(self, transitions):
        if transitions is None or len(transitions) == 0:
            return

        filtered = self.__status_changes__(*transitions)

        self.all_environments = set(filtered.keys())
        self.environments = OrderedDict({build: self.all_environments for build in self.builds})
        self.__regressions__ = None
        self.__fixes__ = None
        self.__diff__ = None

        if len(filtered) == 0:
            self.results = OrderedDict()
            return

        # filter results
        all_tests = set(reduce(lambda a, b: a + b, filtered.values()))
        self.results = OrderedDict({full_name: self.results[full_name] for full_name in all_tests})
        self.results = OrderedDict(sorted(self.results.items()))

    def __status_changes__(self, *transitions, predicate=lambda test, env: True):
        if len(self.builds) < 2:
            return {}

        comparisons = OrderedDict()
        after = self.builds[-1]  # last
        before = self.builds[-2]  # second to last
        for env in self.all_environments:
            comparison_list = []
            for test, results in self.diff.items():
                results_after = results.get((after, env), 'n/a')
                results_before = results.get((before, env), 'n/a')
                if (results_before, results_after) in transitions:
                    if predicate(test, env):
                        comparison_list.append(test)
            if comparison_list:
                comparisons[env] = comparison_list

        return comparisons

    @property
    def regressions_grouped_by_suite(self):
        return self.__status_changes_by_suite__()

    @property
    def fixes_grouped_by_suite(self):
        return self.__status_changes_by_suite__(False)

    def __status_changes_by_suite__(self, regression=True):
        comparisons = self.regressions
        if not regression:
            comparisons = self.fixes
        result = OrderedDict()
        for env, tests in comparisons.items():
            this_env = OrderedDict()
            for test in tests:
                suite, testname = parse_name(test)
                if suite not in this_env:
                    this_env[suite] = []
                this_env[suite].append(testname)
            result[env] = this_env
        return result

    def __regressions_and_fixes__(self, baseline_build, target_build):
        # Calculate regressions and fixes directly in the database
        # awfully ugly but lightning fast
        # FIXME if Django comes up with a better solution using ORM
        select_baseline_tests = '' \
            ' SELECT DISTINCT ' \
            '     baseline_test.id AS id,' \
            '     baseline_test.suite_id,' \
            '     baseline_test.name,' \
            '     baseline_test.result,' \
            '     baseline_test.has_known_issues,' \
            '     baseline_test.test_run_id '

        select_target_tests = '' \
            ' SELECT DISTINCT' \
            '     target_test.id AS id,' \
            '     target_test.suite_id,' \
            '     target_test.name,' \
            '     target_test.result,' \
            '     target_test.has_known_issues,' \
            '     target_test.test_run_id '

        from_where = '' \
            ' FROM ' \
            '     core_test    baseline_test,' \
            '     core_testrun baseline_testrun,' \
            '     core_test    target_test,' \
            '     core_testrun target_testrun' \
            ' WHERE ' \
            '     baseline_test.test_run_id = baseline_testrun.id AND' \
            '     target_test.test_run_id   = target_testrun.id AND' \
            '     baseline_testrun.environment_id = target_testrun.environment_id AND' \
            '     baseline_test.name              = target_test.name AND' \
            '     baseline_test.suite_id          = target_test.suite_id AND' \
            '     baseline_test.result <> target_test.result AND' \
            '     baseline_testrun.build_id = %s AND target_testrun.build_id = %s '

        order_by = ' ORDER BY id '
        sql = select_baseline_tests + from_where + ' UNION ' + select_target_tests + from_where + order_by
        differing_tests = models.Test.objects.raw(sql, [baseline_build.id, target_build.id, baseline_build.id, target_build.id])

        # Django 1.11 compatibility (only 2.0+ allow prefetch_related on raw queries)
        ids = [t.id for t in differing_tests]
        tests = models.Test.objects.filter(id__in=ids)

        self.environments = OrderedDict()
        self.environments[baseline_build] = set()
        self.environments[target_build] = set()
        self.all_environments = set()
        self.results = OrderedDict()
        for t in tests.prefetch_related('test_run', 'suite', 'test_run__environment', 'test_run__build'):
            env = str(t.test_run.environment)
            self.all_environments.add(env)
            self.environments[t.test_run.build].add(env)
            key = (t.test_run.build, env)
            full_name = join_name(t.suite.slug, t .name)
            if full_name not in self.results:
                self.results[full_name] = OrderedDict()
            self.results[full_name][key] = t.status
            if t.has_known_issues and t.known_issues.filter(intermittent=True):
                self.__intermittent__[(full_name, env)] = True

        self.results = OrderedDict(sorted(self.results.items()))
        self.environments[baseline_build] = sorted(self.environments[baseline_build])
        self.environments[target_build] = sorted(self.environments[target_build])
