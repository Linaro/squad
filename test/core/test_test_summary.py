from django.test import TestCase
from unittest.mock import patch


from squad.core.models import Group, Build, TestSummary, KnownIssue


class TestSummaryTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')

    def test_basics(self):
        build = self.project.builds.create(version='1')
        env = self.project.environments.create(slug='env')
        suite = self.project.suites.create(slug='tests')
        test_run = build.test_runs.create(environment=env)
        test_run.tests.create(name='foo', suite=suite, result=True)
        test_run.tests.create(name='bar', suite=suite, result=False)
        test_run.tests.create(name='baz', suite=suite, result=None)
        test_run.tests.create(name='qux', suite=suite, result=False)
        test_run.tests.create(name='pla', suite=suite, result=False, has_known_issues=True)

        summary = TestSummary(build)
        self.assertEqual(5, summary.tests_total)
        self.assertEqual(1, summary.tests_pass)
        self.assertEqual(2, summary.tests_fail)
        self.assertEqual(1, summary.tests_skip)
        self.assertEqual(1, summary.tests_xfail)
        self.assertEqual(['tests/bar', 'tests/qux'], sorted([t.full_name for t in summary.failures['env']]))

    def test_test_summary_retried_tests(self):
        build = Build.objects.create(project=self.project, version='1.1')
        env = self.project.environments.create(slug='env')
        suite = self.project.suites.create(slug='tests')
        test_run1 = build.test_runs.create(environment=env)
        test_run2 = build.test_runs.create(environment=env)

        test_run1.tests.create(name='foo', suite=suite, result=True)
        test_run2.tests.create(name='foo', suite=suite, result=True)

        summary = build.test_summary
        self.assertEqual(1, summary.tests_total)
        self.assertEqual(1, summary.tests_pass)

    def test_later_test_prevails(self):
        build = Build.objects.create(project=self.project, version='1.1')
        env = self.project.environments.create(slug='env')
        suite = self.project.suites.create(slug='tests')
        test_run1 = build.test_runs.create(environment=env)
        test_run2 = build.test_runs.create(environment=env)

        test_run1.tests.create(name='foo', suite=suite, result=True)
        test_run2.tests.create(name='foo', suite=suite, result=False)

        summary = build.test_summary
        self.assertEqual(1, summary.tests_total)
        self.assertEqual(0, summary.tests_pass)
        self.assertEqual(1, summary.tests_fail)

    def test_counts_separate_environments_separately(self):
        build = Build.objects.create(project=self.project, version='1.1')
        env1 = self.project.environments.create(slug='env1')
        env2 = self.project.environments.create(slug='env2')
        suite = self.project.suites.create(slug='tests')
        test_run_env1 = build.test_runs.create(environment=env1)
        test_run_env2 = build.test_runs.create(environment=env2)

        test_run_env1.tests.create(name='foo', suite=suite, result=True)
        test_run_env2.tests.create(name='foo', suite=suite, result=False)

        summary = build.test_summary
        self.assertEqual(2, summary.tests_total)
        self.assertEqual(1, summary.tests_pass)
        self.assertEqual(1, summary.tests_fail)
