from django.shortcuts import render

from squad.http import auth
from squad.core.models import Group, Test
from squad.core.history import TestHistory
from django.shortcuts import get_object_or_404


class TestResult(object):

    def __init__(self, name):
        self.name = name
        self.results = []

    def add(self, result):
        self.results.append(result)

    @property
    def failure(self):
        return any([r == 'fail' for r in self.results])


class TestResultTable(object):

    def __init__(self):
        self.environments = None
        self.failures = []
        self.non_failures = []

    def __bool__(self):
        return bool(self.failures) or bool(self.non_failures)

    def add(self, test):
        if test.failure:
            self.failures.append(test)
        else:
            self.non_failures.append(test)

    @classmethod
    def get(cls, build):
        table = cls()
        table.environments = set([t.environment for t in build.test_runs.prefetch_related('environment').all()])

        tests = Test.objects.filter(
            test_run__build=build
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
                test_result.add(results.get(env.id, "n/a"))
            table.add(test_result)

        return table


@auth
def tests(request, group_slug, project_slug, build_version):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)
    build = get_object_or_404(project.builds, version=build_version)

    context = {
        "project": project,
        "build": build,
        "results": TestResultTable.get(build),
    }

    return render(request, 'squad/tests.html', context)


@auth
def test_history(request, group_slug, project_slug, full_test_name):
    group = Group.objects.get(slug=group_slug)
    project = group.projects.get(slug=project_slug)

    history = TestHistory(project, full_test_name)
    context = {
        "project": project,
        "history": history,
    }
    return render(request, 'squad/test_history.html', context)
