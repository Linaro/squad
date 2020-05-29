import json

from django.db.models import Prefetch
from django.shortcuts import render, get_object_or_404
from django.http import Http404

from squad.http import auth
from squad.core.models import Test, Suite, TestRun
from squad.core.history import TestHistory
from squad.core.utils import split_list
from squad.frontend.views import get_build


class TestResult(list):
    """
    A List of pass/fail/skip statuses, one per environment. Represents one row
    of the test results table.
    """

    def __init__(self, name, test_run=None, suite=None):
        self.name = name
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
        self.paginator = self
        self.paginator.num_pages = 0
        self.number = 0
        self.all_tests = []

    def __get_all_tests__(self, build, search):

        test_runs = TestRun.objects.filter(build=build).values('id')
        test_runs_ids = [test_run['id'] for test_run in test_runs]
        for chunk in split_list(test_runs_ids, chunk_size=100):
            query_set = Test.objects.filter(test_run_id__in=chunk).prefetch_related('suite')
            if search:
                query_set = query_set.filter(name__icontains=search)

            tests = query_set.only('id', 'suite', 'name', 'result', 'has_known_issues').order_by()
            self.all_tests += tests

    # count how many unique tests are represented in the given build, and sets
    # pagination data
    def __count_pages__(self, per_page):
        distinct_tests = set([(test.suite.id, test.name) for test in self.all_tests])
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

        stats = {}
        for test in self.all_tests:
            if test.full_name not in stats:
                stats[test.full_name] = {'pass': 0, 'fail': 0, 'xfail': 0, 'skip': 0, 'ids': []}
            stats[test.full_name][test.status] += 1
            stats[test.full_name]['ids'].append(test.id)

        def keyfunc(item):
            name = item[0]
            statuses = item[1]
            return tuple((-statuses[k] for k in ['fail', 'xfail', 'skip', 'pass'])) + (name,)

        ordered = sorted(stats.items(), key=keyfunc)
        tests_in_page = ordered[offset:offset + per_page]

        tests_ids = []
        for test in tests_in_page:
            tests_ids += test[1]['ids']

        return tests_ids

    @classmethod
    def get(cls, build, page, search, per_page=50):
        table = cls()
        table.__get_all_tests__(build, search)
        table.number = page
        table.__count_pages__(per_page)

        table.environments = set([t.environment for t in build.test_runs.prefetch_related('environment').all()])

        tests = Test.objects.filter(
            id__in=table.__get_page_filter__(page, per_page)
        ).prefetch_related(
            Prefetch('test_run', queryset=TestRun.objects.only('environment')),
            'suite',
            'suite__metadata',
            'metadata',
        )

        memo = {}
        for test in tests:
            memo.setdefault(test, {})
            memo[test][test.test_run.environment_id] = [test.status]

            error_info = {
                "test_description": test.metadata.description if test.metadata else '',
                "suite_instructions": test.suite.metadata.instructions_to_reproduce if test.suite.metadata else '',
                "test_instructions": test.metadata.instructions_to_reproduce if test.metadata else '',
                "test_log": test.log or '',
            }
            info = json.dumps(error_info) if any(error_info.values()) else None

            memo[test][test.test_run.environment_id].append(info)

        for test, results in memo.items():
            test_result = TestResult(test.name, test.test_run, test.suite)
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

    search = request.GET.get('search', '')

    context = {
        "project": project,
        "build": build,
        "search": search,
        "results": TestResultTable.get(build, page, search),
    }

    return render(request, 'squad/tests.jinja2', context)


@auth
def test_history(request, group_slug, project_slug, build_version, testrun, suite_slug, test_name):
    project = request.project
    build = get_build(project, build_version)
    test_run = get_object_or_404(build.test_runs, pk=testrun)
    suite_slug = suite_slug.replace('$', '/')
    suite = get_object_or_404(project.suites, slug=suite_slug)
    status = get_object_or_404(test_run.status, suite=suite)
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    top = request.GET.get('top', None)
    if top:
        top = get_build(project, top)

    try:
        full_test_name = "/".join([suite_slug, test_name])
        history = TestHistory(project, full_test_name, top=top, page=page)
        context = {
            "project": project,
            "history": history,
            "build": build,
            "status": status,
            "test": test_name
        }
        return render(request, 'squad/test_history.jinja2', context)
    except Suite.DoesNotExist:
        raise Http404("No such suite for test: %s")
