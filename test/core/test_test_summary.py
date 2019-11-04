from django.test import TestCase

from squad.core.models import Group, Build, TestSummary, KnownIssue
from squad.core.tasks import ReceiveTestRun


class TestSummaryTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.receive_testrun = ReceiveTestRun(self.project, update_project_status=False)

    def test_basics(self):
        build = self.project.builds.create(version='1')
        env = self.project.environments.create(slug='env')

        known_issue = KnownIssue.objects.create(title='dummy_issue', test_name='tests/pla')
        known_issue.environments.add(env)
        known_issue.save()

        tests_json = """
            {
                "tests/foo": "pass",
                "tests/bar": "fail",
                "tests/baz": "none",
                "tests/qux": "fail",
                "tests/pla": "fail"
            }
        """
        self.receive_testrun(build.version, env.slug, tests_file=tests_json)

        summary = TestSummary(build)
        self.assertEqual(5, summary.tests_total)
        self.assertEqual(1, summary.tests_pass)
        self.assertEqual(2, summary.tests_fail)
        self.assertEqual(1, summary.tests_skip)
        self.assertEqual(1, summary.tests_xfail)

    def test_test_summary_retried_tests(self):
        build = Build.objects.create(project=self.project, version='1.1')
        env = self.project.environments.create(slug='env')

        self.receive_testrun(build.version, env.slug, tests_file='{"tests/foo": "pass"}')
        self.receive_testrun(build.version, env.slug, tests_file='{"tests/foo": "pass"}')

        summary = build.test_summary
        self.assertEqual(2, summary.tests_total)
        self.assertEqual(2, summary.tests_pass)

    def test_later_test_does_not_prevails(self):
        build = Build.objects.create(project=self.project, version='1.1')
        env = self.project.environments.create(slug='env')

        self.receive_testrun(build.version, env.slug, tests_file='{"tests/foo": "pass"}')
        self.receive_testrun(build.version, env.slug, tests_file='{"tests/foo": "fail"}')

        summary = build.test_summary
        self.assertEqual(2, summary.tests_total)
        self.assertEqual(1, summary.tests_pass)
        self.assertEqual(1, summary.tests_fail)

    def test_count_separate_environments_separately(self):
        build = Build.objects.create(project=self.project, version='1.1')
        env1 = self.project.environments.create(slug='env1')
        env2 = self.project.environments.create(slug='env2')

        self.receive_testrun(build.version, env1.slug, tests_file='{"tests/foo": "pass"}')
        self.receive_testrun(build.version, env2.slug, tests_file='{"tests/foo": "fail"}')

        summary = build.test_summary
        self.assertEqual(2, summary.tests_total)
        self.assertEqual(1, summary.tests_pass)
        self.assertEqual(1, summary.tests_fail)

    def test_count_single_environment(self):
        build = Build.objects.create(project=self.project, version='1.1')
        env1 = self.project.environments.create(slug='env1')
        env2 = self.project.environments.create(slug='env2')

        self.receive_testrun(build.version, env1.slug, tests_file='{"tests/foo": "pass"}')
        self.receive_testrun(build.version, env2.slug, tests_file='{"tests/foo": "fail"}')

        summary = TestSummary(build, env1)
        self.assertEqual(1, summary.tests_total)
        self.assertEqual(1, summary.tests_pass)
        self.assertEqual(0, summary.tests_fail)
