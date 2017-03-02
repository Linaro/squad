from collections import OrderedDict


from squad.core.models import Build


class TestComparison(object):

    def __init__(self, *builds):
        self.builds = list(builds)
        self.test_runs = OrderedDict()
        self.results = OrderedDict()

        Build.prefetch_related(self.builds)
        self.__extract_test_runs__()

    @classmethod
    def compare_builds(cls, *builds):
        return cls(*builds)

    @classmethod
    def compare_projects(cls, *projects):
        builds = [p.builds.last() for p in projects]
        return cls.compare_builds(*builds)

    def __extract_test_runs__(self):
        for build in self.builds:
            if not build:
                continue
            self.test_runs[build] = list(build.test_runs.all())
            for test_run in self.test_runs[build]:
                self.__extract_test_results__(test_run)

    def __extract_test_results__(self, test_run):
        tests = sorted(test_run.tests.all(), key=lambda t: t.full_name)
        for test in tests:
            if test.full_name not in self.results:
                self.results[test.full_name] = OrderedDict()
            self.results[test.full_name][test_run] = test.status
