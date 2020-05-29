from collections import OrderedDict
from django.core.paginator import Paginator


from squad.core.utils import parse_name
from squad.core.models import Test


class TestResult(object):

    __test__ = False

    def __init__(self, test):
        self.test = test
        self.suite = test.suite
        self.known_issues = test.known_issues.all()
        self.status = test.status
        self.test_run = test.test_run
        self.info = {
            "test_description": test.metadata.description if test.metadata else '',
            "suite_instructions": test.suite.metadata.instructions_to_reproduce if test.suite.metadata else '',
            "test_instructions": test.metadata.instructions_to_reproduce if test.metadata else '',
            "test_log": test.log
        }


class TestHistory(object):

    __test__ = False

    def __init__(self, project, full_test_name, top=None, page=1, per_page=20):
        suite, test_name = parse_name(full_test_name)
        self.test = full_test_name

        self.paginator = Paginator(project.builds.reverse(), per_page)
        if top:
            self.number = 0
            builds = project.builds.filter(datetime__lte=top.datetime).reverse()[0:per_page - 1]
        else:
            self.number = page
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
        self.top = builds[0]

        for test in tests:
            build = test.test_run.build
            environment = test.test_run.environment

            environments[environment] = True
            results[build][environment] = TestResult(test)

        self.environments = sorted(environments.keys(), key=lambda env: env.slug)
        self.results = results
