from collections import OrderedDict
from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.db.models.query import prefetch_related_objects

from squad.core.queries import test_confidence
from squad.core.utils import parse_name, split_list
from squad.core.models import Test, SuiteMetadata, TestRun, KnownIssue


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

    def __get_tests__(self, builds, metadata):
        test_runs = []
        for build in builds:
            for test_run in build.test_runs.all():
                test_runs.append(test_run)

        tests = []
        for test_runs_batch in split_list(test_runs, chunk_size=100):
            prefetch_related_objects(test_runs_batch, Prefetch('tests', queryset=Test.objects.filter(metadata=metadata).prefetch_related('metadata').order_by()))
            for test_run in test_runs_batch:
                tests += test_run.tests.all()
        return tests

    def __init__(self, project, full_test_name, top=None, page=1, per_page=20):
        suite_slug, test_name = parse_name(full_test_name)
        self.test = full_test_name

        self.paginator = Paginator(project.builds.prefetch_related(Prefetch('test_runs', queryset=TestRun.objects.prefetch_related('environment').all())).reverse(), per_page)
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
        tests = self.__get_tests__(builds, metadata)
        all_envs = set(project.environments.all())
        for test in tests:
            build = test.test_run.build
            environment = test.test_run.environment
            environments[environment] = True
            known_issues = issues_by_env.get(environment.id)
            is_duplicate = False
            if environment in results[build]:
                is_duplicate = True
            results[build][environment] = TestResult(test, suite, metadata, known_issues, is_duplicate)

        for build in results.keys():
            recorded_envs = set(results[build].keys())
            remaining_envs = all_envs - recorded_envs
            for env in remaining_envs:
                results[build][env] = None
                environments[env] = True
        # Make sure all builds that don't have the test have None at least
        for b in builds:
            if not results[b]:
                for env in all_envs:
                    results[build][env] = None
                    environments[env] = True

        self.environments = sorted(environments.keys(), key=lambda env: env.slug)
        self.results = results
