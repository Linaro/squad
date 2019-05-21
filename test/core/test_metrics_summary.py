from django.test import TestCase


from squad.core.models import Group, MetricsSummary
from squad.core.statistics import geomean


PRECISION_ERROR = 10e-9


def eq(num1, num2):
    return abs(num1 - num2) < PRECISION_ERROR


class MetricsSummaryTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.build1 = self.project.builds.create(version='1')
        self.build2 = self.project.builds.create(version='2')
        self.env1 = self.project.environments.create(slug='env1')
        self.env2 = self.project.environments.create(slug='env2')
        suite1 = self.project.suites.create(slug='suite1')
        suite2 = self.project.suites.create(slug='suite2')

        test_run1 = self.build1.test_runs.create(environment=self.env1)
        test_run1.metrics.create(name='foo', suite=suite1, result=1)
        test_run1.metrics.create(name='bar', suite=suite1, result=2)
        test_run1.metrics.create(name='baz', suite=suite2, result=3)
        test_run1.metrics.create(name='qux', suite=suite2, result=4)

        test_run2 = self.build1.test_runs.create(environment=self.env2)
        test_run2.metrics.create(name='foo', suite=suite1, result=2)
        test_run2.metrics.create(name='bar', suite=suite1, result=4)
        test_run2.metrics.create(name='baz', suite=suite2, result=6)
        test_run2.metrics.create(name='qux', suite=suite2, result=8)

    def test_empty_metrics(self):
        summary = MetricsSummary(self.build2)
        self.assertFalse(summary.has_metrics)

    def test_basic_summary(self):
        values = [1, 2, 3, 4, 2, 4, 6, 8]
        summary = MetricsSummary(self.build1)

        self.assertTrue(summary.has_metrics)
        self.assertTrue(eq(geomean(values), summary.value))

    def test_environment_summary(self):
        values1 = [1, 2, 3, 4]
        values2 = [2, 4, 6, 8]
        summary1 = MetricsSummary(self.build1, self.env1)
        summary2 = MetricsSummary(self.build1, self.env2)

        self.assertTrue(summary1.has_metrics)
        self.assertTrue(summary2.has_metrics)
        self.assertTrue(eq(geomean(values1), summary1.value))
        self.assertTrue(eq(geomean(values2), summary2.value))
