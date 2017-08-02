from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.utils import timezone

from unittest.mock import patch
from squad.core.models import Group, Test, Suite


class TestTest(TestCase):

    @patch("squad.core.models.join_name", lambda x, y: 'woooops')
    def test_full_name(self):
        s = Suite()
        t = Test(suite=s)
        self.assertEqual('woooops', t.full_name)

    def test_status_na(self):
        t = Test(result=None)
        self.assertEqual('skip', t.status)

    def test_status_pass(self):
        t = Test(result=True)
        self.assertEqual('pass', t.status)

    def test_status_fail(self):
        t = Test(result=False)
        self.assertEqual('fail', t.status)


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
        test = test_run.tests.create(suite=self.suite, name=test, result=result)

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
