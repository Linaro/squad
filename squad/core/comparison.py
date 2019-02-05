from collections import OrderedDict
from django.db.models import F


from squad.core.utils import parse_name
from squad.core import models
from squad.core.utils import join_name


class TestComparison(object):
    """
    Data structure:

    builds: [Build]
    environments: Build → [EnvironmentName(str)]
    results: TestName(str) → ((Build,EnvironmentName(str)) → TestResults)

    The best way to think about this is to think of the table you want as
    result:

    +-------+---------------+---------------+
    |       |    build 1    |    build 2    |
    +       +-------+-------+-------+-------+
    |       | env 1 | env 2 | env 1 | env 2 |
    +-------+-------+-------+-------+-------+
    | test1 |       |       |       |       |
    | test2 |       |       |       |       |
    | test3 |       |       |       |       |
    | test4 |       |       |       |       |
    +-------+-------+-------+-------+-------+

    `builds` is the list of builds (the top header row)

    `environments` is a mapping between a build and the list of environments
    (the bottom header row)

    `results` contains the body of the table. It is a mapping between a test
    name string (row) to the results for that row. results[testname] is then a
    mapping, between Environment (the column) and the test result (the cells in
    the table). So results[testname][env] gives you the value of the cell at
    (testname, env)
    """

    def __init__(self, *builds):
        self.builds = list(builds)
        self.environments = OrderedDict()
        self.all_environments = set()
        self.results = OrderedDict()
        self.__intermittent__ = {}

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
        test_runs = models.TestRun.objects.filter(
            build__in=self.builds,
        ).prefetch_related(
            'build',
            'environment',
        )
        for build in self.builds:
            self.environments[build] = set()
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
            suite_slug=F('suite__slug')
        )
        for test in tests.iterator():
            key = (test_run.build, str(test_run.environment))
            test_full_name = join_name(test.suite_slug, test.name)
            if test_full_name not in self.results:
                self.results[test_full_name] = OrderedDict()
            self.results[test_full_name][key] = test.status
            if test.has_known_issues:
                for issue in test.known_issues.all():
                    if issue.intermittent:
                        env = str(test_run.environment)
                        self.__intermittent__[(test_full_name, env)] = True

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
        for test, results in self.results.items():
            previous = None
            for build in self.builds:
                current = [results.get((build, e)) for e in self.environments[build]]
                if previous and previous != current:
                    d[test] = results
                    break
                previous = current

        self.__diff__ = d
        return self.__diff__

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

    def __status_changes__(self, *transitions, predicate=lambda test, env: True):
        if len(self.builds) < 2:
            return {}

        comparisons = OrderedDict()
        after = self.builds[-1]  # last
        before = self.builds[-2]  # second to last
        for env in self.environments[after]:
            comparison_list = []
            for test, results in self.diff.items():
                results_after = results.get((after, env))
                results_before = results.get((before, env))
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
