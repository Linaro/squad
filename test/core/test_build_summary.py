from django.test import TestCase


from squad.core.models import Group, BuildSummary, KnownIssue, SuiteMetadata
from squad.core.statistics import geomean
from squad.core.tasks import ReceiveTestRun


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

        foo_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite1.slug, name='foo', kind='metric')
        bar_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite1.slug, name='bar', kind='metric')
        baz_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite2.slug, name='baz', kind='metric')
        qux_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite2.slug, name='qux', kind='metric')

        test_run1 = self.build1.test_runs.create(environment=self.env1)
        test_run1.metrics.create(metadata=foo_metadata, suite=self.suite1, result=1, build=test_run1.build, environment=test_run1.environment)
        test_run1.metrics.create(metadata=bar_metadata, suite=self.suite1, result=2, build=test_run1.build, environment=test_run1.environment)
        test_run1.metrics.create(metadata=baz_metadata, suite=self.suite2, result=3, build=test_run1.build, environment=test_run1.environment)
        test_run1.metrics.create(metadata=qux_metadata, suite=self.suite2, result=4, build=test_run1.build, environment=test_run1.environment)

        test_run2 = self.build1.test_runs.create(environment=self.env2)
        test_run2.metrics.create(metadata=foo_metadata, suite=self.suite1, result=2, build=test_run2.build, environment=test_run2.environment)
        test_run2.metrics.create(metadata=bar_metadata, suite=self.suite1, result=4, build=test_run2.build, environment=test_run2.environment)
        test_run2.metrics.create(metadata=baz_metadata, suite=self.suite2, result=6, build=test_run2.build, environment=test_run2.environment)
        test_run2.metrics.create(metadata=qux_metadata, suite=self.suite2, result=8, build=test_run2.build, environment=test_run2.environment)

        known_issue = KnownIssue.objects.create(title='dummy_issue', test_name='suite2/qux')
        known_issue.environments.add(self.env1)
        known_issue.save()

        tests_json = """
            {
                "suite1/foo": "pass",
                "suite1/bar": "fail",
                "suite2/baz": "none",
                "suite2/qux": "fail"
            }
        """
        self.receive_testrun = ReceiveTestRun(self.project, update_project_status=False)
        self.receive_testrun(self.build1.version, self.env1.slug, tests_file=tests_json)

        tests_json = """
            {
                "suite1/foo": "pass",
                "suite1/bar": "fail",
                "suite2/baz": "none"
            }
        """
        self.receive_testrun(self.build1.version, self.env2.slug, tests_file=tests_json)

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
        new_foo_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite1.slug, name='new_foo', kind='metric')
        new_test_run.metrics.create(metadata=new_foo_metadata, suite=self.suite1, result=5, build=new_test_run.build, environment=new_test_run.environment)

        self.receive_testrun(self.build1.version, self.env1.slug, tests_file='{"suite1/new_foo": "pass"}')

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
