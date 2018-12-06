from django.db import connection
from django.db.models import Q
from django.shortcuts import render

from squad.http import auth
from squad.core.models import Group, Test, Suite
from squad.core.history import TestHistory
from django.shortcuts import get_object_or_404
from django.http import Http404
from squad.frontend.views import get_build


class TestResult(list):
    """
    A List of pass/fail/skip statuses, one per environment. Represents one row
    of the test results table.
    """

    def __init__(self, name):
        self.name = name
        self.totals = {"pass": 0, "fail": 0, "xfail": 0, "skip": 0, "n/a": 0}

    def append(self, item):
        self.totals[item] += 1
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

    # count how many unique tests are represented in the given build, and sets
    # pagination data
    def __count_pages__(self, build_id, per_page):
        query = """
            SELECT COUNT(*)
            FROM (
                SELECT distinct suite_id, name
                FROM core_test
                JOIN core_testrun ON core_testrun.id = core_test.test_run_id
                WHERE core_testrun.build_id = %s
            ) unique_tests
        """
        with connection.cursor() as cursor:
            cursor.execute(query, [build_id])
            count = cursor.fetchone()[0]
            # count pages
            self.num_pages = count // per_page
            if count % per_page > 0:
                self.num_pages += 1

    def __get_page_filter__(self, build_id, page, per_page):
        """
        Query to obtain one page os test results. It is used to know which tests
        should be in the page. It's ordered so that the tests with more failures
        come first, then tests with less failures, then tests with more skips.

        After the tests in the page have been determined here, a new query is
        needed to obtain the data about per-environment test results.
        """

        conditions = {}
        offset = (page - 1) * per_page

        query = """
        SELECT
          suite_id,
          core_test.name,
          SUM(CASE when result is null then 1 else 0 end) as skips,
          SUM(CASE when result is not null and not result and (has_known_issues is null or not has_known_issues) then 1 else 0 end) as fails,
          SUM(CASE when result is not null and not result and has_known_issues then 1 else 0 end) as xfails,
          SUM(CASE when result is null then 0 when result then 1 else 0 end) as passes
        FROM core_test
        JOIN core_testrun ON core_testrun.id = core_test.test_run_id
        JOIN core_suite ON core_test.suite_id = core_suite.id
        WHERE core_testrun.build_id = %s
        GROUP BY suite_id, core_suite.slug, core_test.name
        ORDER BY fails DESC, xfails DESC, skips DESC, passes DESC, core_suite.slug, core_test.name
        LIMIT %s
        OFFSET %s
        """
        with connection.cursor() as cursor:
            cursor.execute(query, [build_id, per_page, offset])
            for suite_id, name, _, _, _, _ in cursor.fetchall():
                conditions.setdefault(suite_id, [])
                conditions[suite_id].append(name)

        the_filter = Q(id__lt=0)  # always false
        for suite_id, names in conditions.items():
            new_filter = (Q(suite_id=suite_id) & Q(name__in=names))
            the_filter = the_filter | new_filter

        return the_filter

    @classmethod
    def get(cls, build, page, per_page=50):
        table = cls()
        table.number = page
        table.__count_pages__(build.id, per_page)

        table.environments = set([t.environment for t in build.test_runs.prefetch_related('environment').all()])

        tests = Test.objects.filter(
            test_run__build=build
        ).filter(
            table.__get_page_filter__(build.id, page, per_page)
        ).prefetch_related(
            'test_run',
            'suite',
        ).order_by('suite_id', 'name')
        memo = {}
        for test in tests:
            memo.setdefault(test.full_name, {})
            memo[test.full_name][test.test_run.environment_id] = test.status
        for name, results in memo.items():
            test_result = TestResult(name)
            for env in table.environments:
                test_result.append(results.get(env.id, "n/a"))
            table.append(test_result)

        table.sort()

        return table


@auth
def tests(request, group_slug, project_slug, build_version):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = get_build(project, build_version)

    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    context = {
        "project": project,
        "build": build,
        "results": TestResultTable.get(build, page),
    }

    return render(request, 'squad/tests.jinja2', context)


@auth
def test_history(request, group_slug, project_slug, full_test_name):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)

    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    top = request.GET.get('top', None)
    if top:
        top = get_build(project, top)

    try:
        history = TestHistory(project, full_test_name, top=top, page=page)
        context = {
            "project": project,
            "history": history,
        }
        return render(request, 'squad/test_history.jinja2', context)
    except Suite.DoesNotExist:
        raise Http404("No such suite for test: %s")
