from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.utils import timezone

from unittest.mock import patch
from squad.core.models import Group, Test, Suite, SuiteMetadata


def create_test(**kwargs):
    group = Group.objects.create(slug='mygroup')
    project = group.projects.create(slug='myproject')
    build = project.builds.create(version='1')
    environment = project.environments.create(slug='myenv')
    test_run = build.test_runs.create(environment=environment)
    suite = Suite.objects.create(slug='the-suite', project=project)
    opts = {'test_run': test_run, 'suite': suite, 'build': build, 'environment': environment}
    opts.update(kwargs)
    return Test.objects.create(**opts)


class TestTest(TestCase):

    @patch("squad.core.models.join_name", lambda x, y: 'woooops')
    def test_full_name(self):
        t = create_test()
        self.assertEqual('woooops', t.full_name)

    def test_status_na(self):
        t = create_test(result=None)
        self.assertEqual('skip', t.status)

    def test_status_pass(self):
        t = create_test(result=True)
        self.assertEqual('pass', t.status)

    def test_status_fail(self):
        t = create_test(result=False)
        self.assertEqual('fail', t.status)

    def test_status_xfail(self):
        t = create_test(result=False, has_known_issues=True)
        self.assertEqual('xfail', t.status)


class TestFailureHistoryTest(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='group')
        self.project = group.projects.create(slug='project')
        self.suite = self.project.suites.create(slug='suite')
        self.environment = self.project.environments.create(slug='environment')

        self.date = timezone.now()

    def previous_test(self, test, result, environment=None):
        environment = environment or self.environment
        build = self.project.builds.create(
            datetime=self.date,
            version=self.date.strftime("%Y%m%d"),
        )
        test_run = build.test_runs.create(environment=environment)
        metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name=test, kind='test')
        test = test_run.tests.create(suite=self.suite, result=result, metadata=metadata, build=test_run.build, environment=test_run.environment)

        self.date = self.date + relativedelta(days=1)
        return test

    def test_first(self):
        first = self.previous_test("mytest", True)
        current = self.previous_test("mytest", False)
        self.assertEqual(None, current.history.since)
        self.assertEqual(0, current.history.count)
        self.assertEqual(first, current.history.last_different)

    def test_second(self):
        passed = self.previous_test("mytest", True)
        previous = self.previous_test("mytest", False)
        current = self.previous_test("mytest", False)
        self.assertEqual(previous, current.history.since)
        self.assertEqual(1, current.history.count)
        self.assertEqual(passed, current.history.last_different)

    def test_third(self):
        first = self.previous_test("mytest", False)
        self.previous_test("mytest", False)
        current = self.previous_test("mytest", False)
        self.assertEqual(first, current.history.since)
        self.assertEqual(2, current.history.count)

    def test_first_after_previous_regression(self):
        self.previous_test("mytest", False)
        last = self.previous_test("mytest", True)
        current = self.previous_test("mytest", False)
        self.assertEqual(None, current.history.since)
        self.assertEqual(0, current.history.count)
        self.assertEqual(last, current.history.last_different)

    def test_later_tests_dont_influence(self):
        last_pass = self.previous_test("mytest", True)
        first = self.previous_test("mytest", False)
        self.previous_test("mytest", False)
        current = self.previous_test("mytest", False)
        self.previous_test("mytest", True)  # future!
        self.previous_test("mytest", False)  # future!
        self.assertEqual(first, current.history.since)
        self.assertEqual(2, current.history.count)
        self.assertEqual(last_pass, current.history.last_different)

    def test_test_from_another_environment_is_not_considered(self):
        last_pass = self.previous_test("mytest", True)
        first = self.previous_test("mytest", False)

        # test results from another environment
        otherenv = self.project.environments.create(slug='otherenv')
        self.previous_test("mytest", True, otherenv)
        self.previous_test("mytest", False, otherenv)

        current = self.previous_test("mytest", False)
        self.assertEqual(first, current.history.since)
        self.assertEqual(1, current.history.count)
        self.assertEqual(last_pass, current.history.last_different)
