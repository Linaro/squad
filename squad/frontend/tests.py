import json

from collections import defaultdict

from django.shortcuts import render, get_object_or_404
from django.http import Http404

from squad.http import auth
from squad.core.models import Build, Test, Suite, SuiteMetadata, Environment
from squad.core.history import TestHistory
from squad.core.queries import test_confidence
from squad.frontend.views import get_build


class TestResult(list):
    """
    A List of pass/fail/skip statuses, one per environment. Represents one row
    of the test results table.
    """

    def __init__(self, name, test_run=None, suite=None, short_name=None):
        self.name = name
        self.short_name = short_name
        self.test_run = test_run
        self.suite = suite
        self.totals = {"pass": 0, "fail": 0, "xfail": 0, "skip": 0, "n/a": 0}

    def append(self, item):
        self.totals[item[0]] += 1
        return super(TestResult, self).append(item)

    def ordering(self):
        return tuple((-self.totals[k] for k in ("fail", "xfail", "skip", "pass", "n/a"))) + (self.name,)

    def __lt__(self, other):
        return self.ordering() < other.ordering()


class TestResultTable(list):
    """
    A plain list with a few extra attributes. Each list item represents one row
    of the table, and should be an instance of TestResult.

    This class also mimics a Django Paginator so that it can be used with our
    pagination UI.
    """

    def __init__(self):
        self.environments = None
        self.filters = {
            'environment': None,
            'suite': None,
        }
        self.paginator = self
        self.paginator.num_pages = 0
        self.number = 0
        self.all_tests = []

    def __get_all_tests__(self, build, search, env=None, suite=None):

        queryset = Test.objects.filter(build=build)
        if search:
            queryset = queryset.filter(metadata__name__icontains=search)

        if env:
            environment = Environment.objects.filter(project=build.project, slug=env)
            if environment.exists():
                self.filters['environment'] = environment.first()
                queryset = queryset.filter(environment=self.filters['environment'])

        if suite:
            suite_ = Suite.objects.filter(project=build.project, slug=suite)
            if suite_.exists():
                self.filters['suite'] = suite_.first()
                queryset = queryset.filter(suite=self.filters['suite'])

        self.all_tests = queryset.only('result', 'has_known_issues', 'metadata_id').order_by()

    # count how many unique tests are represented in the given build, and sets
    # pagination data
    def __count_pages__(self, per_page):
        distinct_tests = set([test.metadata_id for test in self.all_tests])
        count = len(distinct_tests)
        self.num_pages = count // per_page
        if count % per_page > 0:
            self.num_pages += 1

    def __get_page_filter__(self, page, per_page):
        """
        Query to obtain one page os test results. It is used to know which tests
        should be in the page. It's ordered so that the tests with more failures
        come first, then tests with less failures, then tests with more skips.

        After the tests in the page have been determined here, a new query is
        needed to obtain the data about per-environment test results.
        """
        offset = (page - 1) * per_page

        stats = defaultdict(lambda: {'pass': 0, 'fail': 0, 'xfail': 0, 'skip': 0})
        for test in self.all_tests:
            stats[test.metadata_id][test.status] += 1

        def keyfunc(item):
            metadata_id = item[0]
            statuses = item[1]
            return tuple((-statuses[k] for k in ['fail', 'xfail', 'skip', 'pass'])) + (metadata_id,)

        ordered = sorted(stats.items(), key=keyfunc)
        tests_in_page = ordered[offset:offset + per_page]
        metadata_ids = [t[0] for t in tests_in_page]
        return metadata_ids

    @classmethod
    def get(cls, build, page, search, per_page=50, env=None, suite=None):
        table = cls()
        table.__get_all_tests__(build, search, env=env, suite=suite)
        table.number = page
        table.__count_pages__(per_page)

        if table.filters['environment']:
            table.environments = {table.filters['environment']}
        else:
            table.environments = set([t.environment for t in build.test_runs.prefetch_related('environment').all()])

        queryset = build.tests
        if table.filters['environment']:
            queryset = queryset.filter(environment=table.filters['environment'])

        if table.filters['suite']:
            queryset = queryset.filter(suite=table.filters['suite'])

        tests = queryset.filter(
            metadata_id__in=table.__get_page_filter__(page, per_page),
        ).prefetch_related(
            'suite__metadata',
            'metadata',
        )

        memo = defaultdict(lambda: defaultdict(list))
        for test in tests:
            memo[test.full_name][test.environment_id].append(test)

        # handle duplicates
        for full_name in memo.keys():
            env_ids = memo[full_name].keys()
            for env_id in env_ids:

                test = memo[full_name][env_id][0]

                if len(memo[full_name][env_id]) == 1:
                    memo[full_name][env_id] = [test.status, None]
                else:
                    duplicates = memo[full_name][env_id]
                    memo[full_name][env_id] = list(test_confidence(None, list_of_duplicates=duplicates))

                error_info = {
                    "test_description": test.metadata.description if test.metadata else '',
                    "suite_instructions": test.suite.metadata.instructions_to_reproduce if test.suite.metadata else '',
                    "test_instructions": test.metadata.instructions_to_reproduce if test.metadata else '',
                    "test_log": test.log or '',
                }
                info = json.dumps(error_info) if any(error_info.values()) else None

                memo[full_name][env_id].append(info)

            if 'test_metadata' not in memo[full_name].keys():
                memo[full_name]['test_metadata'] = (test.test_run_id, test.suite, test.name)

        for test_full_name, results in memo.items():
            test_result = TestResult(test_full_name)
            test_result.test_run, test_result.suite, test_result.short_name = results.get('test_metadata', None)
            for env in table.environments:
                test_result.append(results.get(env.id, ["n/a", None]))
            table.append(test_result)

        table.sort()

        return table


@auth
def tests(request, group_slug, project_slug, build_version):
    project = request.project
    build = get_build(project, build_version)

    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    env = request.GET.get('environment')
    suite = request.GET.get('suite')
    search = request.GET.get('search', '')

    context = {
        "project": project,
        "build": build,
        "search": search,
        "results": TestResultTable.get(build, page, search, env=env, suite=suite),
    }

    return render(request, 'squad/tests.jinja2', context)


@auth
def legacy_test_history(request, group_slug, project_slug, full_test_name):
    return test_history(request, group_slug, project_slug, test_name=full_test_name)


@auth
def test_history(request, group_slug, project_slug, build_version=None, testrun_id=None, suite_slug=None, test_name=None):
    project = request.project
    context = {"project": project}
    if build_version and testrun_id and suite_slug:
        build = get_build(project, build_version)
        test_run = get_object_or_404(build.test_runs, pk=testrun_id)
        suite_slug = suite_slug.replace('$', '/')
        suite = get_object_or_404(project.suites, slug=suite_slug)
        status = get_object_or_404(test_run.status, suite=suite)
        full_test_name = "/".join([suite_slug, test_name])
        context.update({"build": build, "status": status, "test": test_name})
    else:
        full_test_name = test_name.replace('$', '/')

    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    top = request.GET.get('top', None)
    if top:
        top = get_build(project, top)
    try:
        history = TestHistory(project, full_test_name, top=top, page=page)
        context.update({"history": history})
        return render(request, 'squad/test_history.jinja2', context)
    except (Suite.DoesNotExist, SuiteMetadata.DoesNotExist, Build.DoesNotExist) as e:
        raise Http404(f"Test not found: {e}")
