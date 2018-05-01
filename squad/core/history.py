from collections import OrderedDict
from django.core.paginator import Paginator


from squad.core.utils import parse_name
from squad.core.models import Test


class TestResult(object):

    def __init__(self, test):
        self.status = test.status
        self.test_run = test.test_run


class TestHistory(object):

    def __init__(self, project, full_test_name, page=1, per_page=20):
        suite, test_name = parse_name(full_test_name)
        self.test = full_test_name

        self.number = page
        self.paginator = Paginator(project.builds.reverse(), per_page)
        builds = self.paginator.page(page)

        suite = project.suites.get(slug=suite)

        tests = Test.objects.filter(
            suite=suite,
            name=test_name,
            test_run__build__in=builds,
        )
        Test.prefetch_related(tests)

        environments = OrderedDict()
        results = OrderedDict()
        for build in builds:
            results[build] = {}

        for test in tests:
            build = test.test_run.build
            environment = test.test_run.environment

            environments[environment] = True
            results[build][environment] = TestResult(test)

        self.environments = list(environments.keys())
        self.results = results
