from collections import defaultdict
from django.core.paginator import Paginator

from squad.core.queries import test_confidence
from squad.core.utils import parse_name
from squad.core.models import SuiteMetadata, KnownIssue, Environment, Build


class TestResult(object):

    __test__ = False

    class TestRunStatus(object):
        def __init__(self, test_run_id, suite):
            self.test_run_id = test_run_id
            self.suite = suite

    def __init__(self, test, suite, metadata, known_issues, is_duplicate=False, list_of_duplicates=None):
        self.test = test
        self.suite = suite
        self.known_issues = known_issues
        if is_duplicate:
            self.status, self.confidence_score = test_confidence(None, list_of_duplicates=list_of_duplicates)
        else:
            self.status, self.confidence_score = (test.status, None)
        self.test_run_id = test.test_run_id
        self.test_run_status = self.TestRunStatus(self.test_run_id, self.suite)
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

        if len(builds) == 0:
            raise Build.DoesNotExist

        self.top = builds[0]

        issues_by_env = {}
        for issue in KnownIssue.active_by_project_and_test(project, full_test_name).all():
            for env in issue.environments.all():
                if env.id not in issues_by_env:
                    issues_by_env[env.id] = []
                issues_by_env[env.id].append(issue)

        suite = project.suites.prefetch_related('metadata').get(slug=suite_slug)
        metadata = SuiteMetadata.objects.get(kind='test', suite=suite_slug, name=test_name)

        results = defaultdict()
        environments_ids = set()
        for build in builds:
            results[build] = defaultdict(list)
            for test in build.tests.filter(metadata=metadata).order_by():
                test.metadata = metadata
                test.suite = suite
                results[build][test.environment_id].append(test)
                environments_ids.add(test.environment_id)

        results_without_duplicates = defaultdict()
        for build in results:
            results_without_duplicates[build] = defaultdict()
            for env in results[build]:
                tests = results[build][env]

                is_duplicate = len(tests) > 1
                known_issues = issues_by_env.get(tests[0].environment_id)
                result = TestResult(tests[0], suite, metadata, known_issues, is_duplicate, list_of_duplicates=tests)
                results_without_duplicates[build][env] = result

        self.environments = Environment.objects.filter(id__in=environments_ids).order_by('slug')
        self.results = results_without_duplicates
