from django.test import TestCase
from unittest.mock import patch


from squad.core.models import Group, Build, TestSummary


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

        summary = TestSummary(build)
        self.assertEqual(4, summary.tests_total)
        self.assertEqual(1, summary.tests_pass)
        self.assertEqual(2, summary.tests_fail)
        self.assertEqual(1, summary.tests_skip)
        self.assertEqual(['tests/bar', 'tests/qux'], sorted([t.full_name for t in summary.failures['env']]))
