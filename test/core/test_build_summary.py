from django.test import TestCase


from squad.core.models import Group, BuildSummary
from squad.core.statistics import geomean


PRECISION_ERROR = 10e-9


def eq(num1, num2):
    return abs(num1 - num2) < PRECISION_ERROR


class BuildSummaryTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.build1 = self.project.builds.create(version='1')
        self.build2 = self.project.builds.create(version='2')
        self.env1 = self.project.environments.create(slug='env1')
        self.env2 = self.project.environments.create(slug='env2')
        self.suite1 = self.project.suites.create(slug='suite1')
        self.suite2 = self.project.suites.create(slug='suite2')

        test_run1 = self.build1.test_runs.create(environment=self.env1)
        test_run1.metrics.create(name='foo', suite=self.suite1, result=1)
        test_run1.metrics.create(name='bar', suite=self.suite1, result=2)
        test_run1.metrics.create(name='baz', suite=self.suite2, result=3)
        test_run1.metrics.create(name='qux', suite=self.suite2, result=4)
        test_run1.tests.create(name='foo', suite=self.suite1, result=True)
        test_run1.tests.create(name='bar', suite=self.suite1, result=False)
        test_run1.tests.create(name='baz', suite=self.suite2, result=None)
        test_run1.tests.create(name='qux', suite=self.suite2, result=False, has_known_issues=True)

        test_run2 = self.build1.test_runs.create(environment=self.env2)
        test_run2.metrics.create(name='foo', suite=self.suite1, result=2)
        test_run2.metrics.create(name='bar', suite=self.suite1, result=4)
        test_run2.metrics.create(name='baz', suite=self.suite2, result=6)
        test_run2.metrics.create(name='qux', suite=self.suite2, result=8)
        test_run2.tests.create(name='foo', suite=self.suite1, result=True)
        test_run2.tests.create(name='bar', suite=self.suite1, result=False)
        test_run2.tests.create(name='baz', suite=self.suite2, result=None)

    def test_build_with_empty_metrics(self):
        summary = BuildSummary.create_or_update(self.build2, self.env1)
        self.assertFalse(summary.has_metrics)

    def test_basic_build_summary(self):
        values1 = [1, 2, 3, 4]
        values2 = [2, 4, 6, 8]
        summary1 = BuildSummary.create_or_update(self.build1, self.env1)
        summary2 = BuildSummary.create_or_update(self.build1, self.env2)

        self.assertTrue(summary1.has_metrics)
        self.assertTrue(summary2.has_metrics)
        self.assertTrue(eq(geomean(values1), summary1.metrics_summary))
        self.assertTrue(eq(geomean(values2), summary2.metrics_summary))

        self.assertEqual(4, summary1.tests_total)
        self.assertEqual(1, summary1.tests_pass)
        self.assertEqual(1, summary1.tests_fail)
        self.assertEqual(1, summary1.tests_skip)
        self.assertEqual(1, summary1.tests_xfail)

        self.assertEqual(3, summary2.tests_total)
        self.assertEqual(1, summary2.tests_pass)
        self.assertEqual(1, summary2.tests_fail)
        self.assertEqual(1, summary2.tests_skip)
        self.assertEqual(0, summary2.tests_xfail)

    def test_update_build_summary(self):
        values1 = [1, 2, 3, 4, 5]
        values2 = [2, 4, 6, 8]
        new_test_run = self.build1.test_runs.create(environment=self.env1)
        new_test_run.metrics.create(name='new_foo', suite=self.suite1, result=5)
        new_test_run.tests.create(name='new_foo', suite=self.suite1, result=True)

        summary1 = BuildSummary.create_or_update(self.build1, self.env1)
        summary2 = BuildSummary.create_or_update(self.build1, self.env2)

        self.assertTrue(summary1.has_metrics)
        self.assertTrue(eq(geomean(values1), summary1.metrics_summary))
        self.assertTrue(summary2.has_metrics)
        self.assertTrue(eq(geomean(values2), summary2.metrics_summary))

        self.assertEqual(5, summary1.tests_total)
        self.assertEqual(2, summary1.tests_pass)
        self.assertEqual(1, summary1.tests_fail)
        self.assertEqual(1, summary1.tests_skip)
        self.assertEqual(1, summary1.tests_xfail)

        self.assertEqual(3, summary2.tests_total)
        self.assertEqual(1, summary2.tests_pass)
        self.assertEqual(1, summary2.tests_fail)
        self.assertEqual(1, summary2.tests_skip)
        self.assertEqual(0, summary2.tests_xfail)
