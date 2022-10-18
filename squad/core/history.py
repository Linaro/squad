from collections import OrderedDict
from django.core.paginator import Paginator

from squad.core.queries import test_confidence
from squad.core.utils import parse_name
from squad.core.models import Test, SuiteMetadata, KnownIssue


class TestResult(object):

    __test__ = False

    class TestRunStatus(object):
        def __init__(self, test_run, suite):
            self.test_run = test_run
            self.suite = suite

    def __init__(self, test, suite, metadata, known_issues, is_duplicate=False):
        self.test = test
        self.suite = suite
        self.known_issues = known_issues
        if is_duplicate:
            self.status, self.confidence_score = test_confidence(test)
        else:
            self.status, self.confidence_score = (test.status, None)
        self.test_run = test.test_run
        self.test_run_status = self.TestRunStatus(self.test_run, self.suite)
        self.info = {
            "test_description": metadata.description if metadata else '',
            "test_instructions": metadata.instructions_to_reproduce if metadata else '',
            "suite_instructions": self.suite.metadata.instructions_to_reproduce if self.suite.metadata else '',
            "test_log": test.log
        }


class TestHistory(object):

    __test__ = False

    def __init__(self, project, full_test_name, top=None, page=1, per_page=20):
        suite_slug, test_name = parse_name(full_test_name)
        self.test = full_test_name

        self.paginator = Paginator(project.builds.reverse(), per_page)
        if top:
            self.number = 0
            builds = project.builds.filter(datetime__lte=top.datetime).reverse()[0:per_page - 1]
        else:
            self.number = page
            builds = self.paginator.page(page)

        self.top = builds[0]

        environments = OrderedDict()
        results = OrderedDict()
        for build in builds:
            results[build] = {}

        issues_by_env = {}
        for issue in KnownIssue.active_by_project_and_test(project, full_test_name).all():
            for env in issue.environments.all():
                if env.id not in issues_by_env:
                    issues_by_env[env.id] = []
                issues_by_env[env.id].append(issue)

        suite = project.suites.prefetch_related('metadata').get(slug=suite_slug)
        metadata = SuiteMetadata.objects.get(kind='test', suite=suite_slug, name=test_name)
        tests = Test.objects.filter(build__in=builds, metadata_id=metadata.id).prefetch_related('build', 'environment', 'test_run', 'metadata').order_by()
        for test in tests:
            build = test.build
            environment = test.environment
            environments[environment] = True
            known_issues = issues_by_env.get(environment.id)
            is_duplicate = False
            if environment in results[build]:
                is_duplicate = True
            results[build][environment] = TestResult(test, suite, metadata, known_issues, is_duplicate)

        self.environments = sorted(environments.keys(), key=lambda env: env.slug)
        self.results = results
