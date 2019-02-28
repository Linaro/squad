import json

from django.db.models import Q, Sum, Case, When
from django.db.models.fields import IntegerField
from django.shortcuts import render

from squad.http import auth
from squad.core.models import Test, Suite
from squad.core.history import TestHistory
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

    # count how many unique tests are represented in the given build, and sets
    # pagination data
    def __count_pages__(self, build_id, search, per_page):
        count = Test.objects.filter(
            test_run__build_id=build_id, name__icontains=search).values(
                'suite_id', 'name').distinct().count()
        self.num_pages = count // per_page
        if count % per_page > 0:
            self.num_pages += 1

    def __get_page_filter__(self, build_id, page, search, per_page):
        """
        Query to obtain one page os test results. It is used to know which tests
        should be in the page. It's ordered so that the tests with more failures
        come first, then tests with less failures, then tests with more skips.

        After the tests in the page have been determined here, a new query is
        needed to obtain the data about per-environment test results.
        """

        conditions = {}
        offset = (page - 1) * per_page

        mylist = Test.objects.filter(
            test_run__build_id=build_id,
            name__icontains=search).values(
                'suite_id', 'suite__slug', 'name').annotate(
                    skips=Sum(Case(
                        When(result__isnull=True, then=1),
                        default=0,
                        output_field=IntegerField())),
                    fails=Sum(Case(
                        When(Q(result__isnull=False) & Q(result=False) & (Q(has_known_issues__isnull=True) | Q(has_known_issues=False)), then=1),
                        default=0,
                        output_field=IntegerField())),
                    xfails=Sum(Case(
                        When(Q(result__isnull=False) & Q(result=False) & Q(has_known_issues=True), then=1),
                        default=0,
                        output_field=IntegerField())),
                    passes=Sum(Case(
                        When(result__isnull=True, then=0),
                        When(result=True, then=1),
                        default=0,
                        output_field=IntegerField()))).order_by(
                            '-fails', '-xfails', '-skips', '-passes',
                            'suite__slug', 'name')[offset:offset + per_page]

        for item in mylist:
            conditions.setdefault(item['suite_id'], [])
            conditions[item['suite_id']].append(item['name'])

        the_filter = Q(id__lt=0)  # always false
        for suite_id, names in conditions.items():
            new_filter = (Q(suite_id=suite_id) & Q(name__in=names))
            the_filter = the_filter | new_filter

        return the_filter

    @classmethod
    def get(cls, build, page, search, per_page=50):
        table = cls()
        table.number = page
        table.__count_pages__(build.id, search, per_page)

        table.environments = set([t.environment for t in build.test_runs.prefetch_related('environment').all()])

        tests = Test.objects.filter(
            test_run__build=build
        ).filter(
            table.__get_page_filter__(build.id, page, search, per_page)
        ).prefetch_related(
            'test_run',
            'suite',
        ).order_by('suite_id', 'name')
        memo = {}
        for test in tests:
            memo.setdefault(test.full_name, {})
            memo[test.full_name][test.test_run.environment_id] = [test.status]
            if test.metadata.description or test.suite.metadata.instructions_to_reproduce or test.metadata.instructions_to_reproduce or test.log:
                error_info = {
                    "test_description": test.metadata.description,
                    "suite_instructions": test.suite.metadata.instructions_to_reproduce,
                    "test_instructions": test.metadata.instructions_to_reproduce,
                    "test_log": test.log
                }
                memo[test.full_name][test.test_run.environment_id].append(
                    json.dumps(error_info))
            else:
                memo[test.full_name][test.test_run.environment_id].append(None)
        for name, results in memo.items():
            test_result = TestResult(name)
            for env in table.environments:
                test_result.append(results.get(
                    env.id, ["n/a", None]))
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
def test_history(request, group_slug, project_slug, full_test_name):
    project = request.project

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
