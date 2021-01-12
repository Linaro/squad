from collections import OrderedDict, defaultdict
from django.db.models import F
from django.db.models import prefetch_related_objects
from itertools import groupby
from functools import reduce
import statistics


from squad.core.queries import test_confidence
from squad.core.utils import parse_name, join_name, split_dict
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
                current = [results.get((build, e))[0] if isinstance(results.get((build, e)), list) else results.get((build, e)) for e in self.environments[build]]
                if previous and previous != current:
                    d[item] = {k: (v[0] if isinstance(v, list) else v) for k, v in results.items()}
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
        self.tests_with_issues = {}
        self.__failures__ = OrderedDict()
        self.regressions_and_fixes_only = regressions_and_fixes_only

        # This is ugly, but it's an easy, light-weight way to compare tests
        # from two builds instead of loading all tests in memory.
        # Please use Django ORM whenever it starts supporting
        # queryies using the same table
        self.base_sql = {
            'select': [
                'target.id',
                'target.build_id',
                'target.environment_id',
                'target.test_run_id',
                'target.suite_id',
                'target.metadata_id',
                'target.result',
                'target.has_known_issues'
            ],
            'from': [
                'core_test baseline',
                'core_test target'
            ],
            'where': [
                'baseline.build_id = {baseline_id}',
                'target.build_id = {target_id}',
                'baseline.metadata_id = target.metadata_id'
            ],
            'values': {
                'baseline_id': '',
                'target_id': ''
            }
        }

        BaseComparison.__init__(self, *builds)

    def __extract_results__(self):

        # New implementation below is only stable for getting regressions and fixes
        # that is used for receiving tests and generating ProjectStatus.regressions and fixes
        # It is still not good for applying transitions and getting a comparison
        # results table, for that, use legacy code, which is slow and eats up lots
        # of memory
        if self.regressions_and_fixes_only:
            self.__new_extract_results__()
            return

        test_runs = models.TestRun.objects.filter(
            build__in=self.builds,
        ).prefetch_related(
            'build',
            'environment',
        ).only('build', 'environment')

        test_runs_ids = {}
        for test_run in test_runs:
            build = test_run.build
            env = test_run.environment.slug

            self.all_environments.add(env)
            self.environments[build].add(env)

            if test_runs_ids.get(test_run.id, None) is None:
                test_runs_ids[test_run.id] = (build, env)

        for ids in split_dict(test_runs_ids, chunk_size=100):
            self.__extract_test_results__(ids)

        self.__resolve_intermittent_tests__()

        self.results = OrderedDict(sorted(self.results.items()))
        for build in self.builds:
            self.environments[build] = sorted(self.environments[build])

    def __extract_test_results__(self, test_runs_ids):
        tests = models.Test.objects.filter(test_run_id__in=test_runs_ids.keys()).annotate(
            suite_slug=F('suite__slug'),
        ).prefetch_related('metadata').defer('log')

        for test in tests:
            build, env = test_runs_ids.get(test.test_run_id)

            full_name = join_name(test.suite_slug, test.name)
            if full_name not in self.results:
                self.results[full_name] = OrderedDict()

            key = (build, env)
            if key in self.results[full_name]:  # Duplicate found.
                if not isinstance(self.results[full_name][key], tuple):
                    # Test confidence is NOT already caclulated.
                    self.results[full_name][key] = test_confidence(test)
            else:
                self.results[full_name][key] = test.status

            if test.has_known_issues:
                self.tests_with_issues[test.id] = (full_name, env)

            if test.status == 'fail' and build.id == self.builds[-1].id:
                if env not in self.__failures__:
                    self.__failures__[env] = []
                self.__failures__[env].append(test)

    def __resolve_intermittent_tests__(self):
        if len(self.tests_with_issues) == 0:
            return

        for chunk in split_dict(self.tests_with_issues, chunk_size=100):
            tests = models.Test.objects.filter(id__in=chunk.keys()).prefetch_related(
                'known_issues'
            ).only('known_issues')
            for test in tests.all():
                for issue in test.known_issues.all():
                    if issue.intermittent:
                        self.__intermittent__[chunk[test.id]] = True
                        break

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

    @property
    def failures(self):
        return self.__failures__

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
            # Let's try to avoid using .diff, it's only used here
            # and in core/notification.py to determine if there is change
            # between builds
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

    def __render_sql__(self, sql):
        select = ', '.join(sql['select'])
        _from = ', '.join(sql['from'])
        where = ' AND '.join(sql['where'])
        values = sql['values']

        sql = 'SELECT %s FROM %s WHERE %s' % (select, _from, where)
        sql = sql.format(**values)

        return sql

    def __new_extract_results__(self):

        sql = self.__get_regressions_and_fixes_sql__()
        tests = [t for t in models.Test.objects.raw(sql)]
        prefetch_related_objects(tests, 'metadata', 'suite')

        env_ids = []
        fixed_tests = defaultdict(set)
        regressions = defaultdict(set)
        fixes = defaultdict(set)

        for test in tests:
            env_id = test.environment_id
            full_name = test.full_name

            env_ids.append(env_id)

            if test.status == 'fail':
                regressions[env_id].add(full_name)
            elif test.status == 'pass':
                fixes[env_id].add(full_name)
                fixed_tests[env_id].add(test.metadata_id)

        environments = {e.id: e for e in models.Environment.objects.filter(id__in=env_ids).all()}

        self.__regressions__ = OrderedDict()
        for env_id in regressions.keys():
            self.__regressions__[environments[env_id].slug] = list(regressions[env_id])

        # It's not a fix if baseline test is intermittent for a given environment:
        # - test.has_known_issues == True and
        # - test.known_issues[env].intermittent == True
        fixed_tests_environment_slugs = [environments[env_id] for env_id in fixed_tests.keys()]
        intermittent_fixed_tests = self.__intermittent_fixed_tests__(fixed_tests, fixed_tests_environment_slugs)
        self.__fixes__ = OrderedDict()
        for env_id in fixes.keys():
            env_slug = environments[env_id].slug
            test_list = [test for test in fixes[env_id] if (test, env_slug) not in intermittent_fixed_tests]
            if len(test_list):
                self.__fixes__[env_slug] = test_list

    def __same_projects__(self):
        if len(self.builds) < 2:
            return True

        baseline = self.builds[0]
        target = self.builds[1]
        return target.project_id == baseline.project_id

    def __get_regressions_and_fixes_sql__(self):
        """
            The target build should be the most recent once and the baseline
            an older build.

            If a test in the target build with result=Fail has a match in the
            baseline build with result=True, it's considered to be a regression.

            If a test in the target build with result=True has a match in the
            baseline build with result=False, it's considered to be a fix.

            |   baseline / target  | test.result == False | test.result == True |
            |----------------------|----------------------|---------------------|
            | test.result == False |         -            |        fix          |
            | test.result == True  |      regression      |         -           |


            We just added a reference to Build and Environment to the Test model so that
            we could make regressions and fixes easy and light to run in the database
        """

        baseline = self.builds[0]
        target = self.builds[1]

        query = self.base_sql.copy()

        # If builds belong to different projects, environment comparison should
        # use slug
        if self.__same_projects__():
            query['where'].append('target.environment_id = baseline.environment_id')
        else:
            query['from'].append('core_environment baseline_environment')
            query['from'].append('core_environment target_environment')
            query['where'].append('target.environment_id = target_environment.id')
            query['where'].append('baseline.environment_id = baseline_environment.id')
            query['where'].append('target_environment.slug = baseline_environment.slug')

        query['where'].append('target.result IS NOT NULL')
        query['where'].append('baseline.result IS NOT NULL')
        query['where'].append('target.result != baseline.result')

        query['values'].update({
            'baseline_id': baseline.id,
            'target_id': target.id
        })

        return self.__render_sql__(query)

    def __intermittent_fixed_tests__(self, fixed_tests, environment_slugs):
        intermittent_fixed_tests = {}
        if len(fixed_tests) == 0:
            return intermittent_fixed_tests

        metadata_ids = []
        for env_id in fixed_tests.keys():
            metadata_ids += list(fixed_tests[env_id])

        baseline = self.builds[0]
        baseline_tests = models.Test.objects.filter(
            build=baseline,
            metadata_id__in=metadata_ids,
            result=False,
            has_known_issues=True
        ).prefetch_related('known_issues', 'suite', 'metadata', 'environment').defer('log').order_by()

        if self.__same_projects__():
            environment_ids = list(fixed_tests.keys())
            baseline_tests = baseline_tests.filter(environment_id__in=environment_ids)
        else:
            baseline_tests = baseline_tests.filter(environment__slug__in=environment_slugs)

        for test in baseline_tests.all():
            for issue in test.known_issues.all():
                if issue.intermittent:
                    key = (test.full_name, test.environment.slug)
                    intermittent_fixed_tests[key] = True

        return intermittent_fixed_tests
