from collections import OrderedDict


from squad.core.utils import join_name
from squad.core.models import Build, Test


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
        self.results = OrderedDict()

        Build.prefetch_related(self.builds)
        self.__extract_results__()

    @classmethod
    def compare_builds(cls, *builds):
        return cls(*builds)

    @classmethod
    def compare_projects(cls, *projects):
        builds = [p.builds.last() for p in projects]
        builds = [b for b in builds if b]
        return cls.compare_builds(*builds)

    def __extract_results__(self):
        for test in self.__all_tests__():
            self.results[test] = OrderedDict()
        for build in self.builds:
            test_runs = list(build.test_runs.all())
            environments = [t.environment for t in test_runs]
            self.environments[build] = sorted([e.slug for e in set(environments)])
            for test_run in test_runs:
                self.__extract_test_results__(test_run)

    def __extract_test_results__(self, test_run):
        for test in test_run.tests.all():
            key = (test_run.build, test_run.environment.slug)
            self.results[test.full_name][key] = test.status

    def __all_tests__(self):
        data = Test.objects.filter(
            test_run__build__project__in=[b.project for b in self.builds]
        ).order_by(
            'suite__slug',
            'name',
        ).values(
            'suite__slug',
            'name',
        ).distinct()
        return sorted([join_name(item['suite__slug'], item['name']) for item in data])

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
