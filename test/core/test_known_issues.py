from django.test import TestCase
from django.utils import timezone

from squad.core.models import Group, KnownIssue, SuiteMetadata
from squad.core.tasks import ParseTestRunData


class KnownIssueTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.env1 = self.project.environments.create(slug='env1')
        self.suite1 = self.project.suites.create(slug="suite1")
        self.suite2 = self.project.suites.create(slug="suite2")
        self.date = timezone.now()

    def test_active_known_issue(self):
        build = self.project.builds.create(
            datetime=self.date,
            version=self.date.strftime("%Y%m%d"),
        )
        test_run = build.test_runs.create(environment=self.env1)
        # create failed test
        foo_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite1.slug, name='test_foo', kind='test')
        test = test_run.tests.create(build=test_run.build, environment=test_run.environment, suite=self.suite1, metadata=foo_metadata, result=False)
        known_issue = KnownIssue.objects.create(
            title="foo",
            test_name=test.full_name
        )
        known_issue.save()
        known_issue.environments.add(test_run.environment)
        self.assertEqual(1, len(KnownIssue.active_by_environment(test_run.environment)))

    def test_inactive_known_issue(self):
        build = self.project.builds.create(
            datetime=self.date,
            version=self.date.strftime("%Y%m%d"),
        )
        test_run = build.test_runs.create(environment=self.env1)
        # create failed test
        foo_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite1.slug, name='test_foo', kind='test')
        test = test_run.tests.create(build=test_run.build, environment=test_run.environment, suite=self.suite1, metadata=foo_metadata, result=False)
        known_issue = KnownIssue.objects.create(
            title="foo",
            test_name=test.full_name
        )
        known_issue.save()
        known_issue.environments.add(test_run.environment)
        known_issue.active = False
        known_issue.save()

        self.assertEqual(0, len(KnownIssue.active_by_environment(self.env1)))

    def test_active_by_project(self):
        build = self.project.builds.create(
            datetime=self.date,
            version=self.date.strftime("%Y%m%d"),
        )
        test_run = build.test_runs.create(environment=self.env1)
        # create failed test
        foo_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite1.slug, name='test_foo', kind='test')
        test = test_run.tests.create(build=test_run.build, environment=test_run.environment, suite=self.suite1, metadata=foo_metadata, result=False)
        known_issue = KnownIssue.objects.create(
            title="foo",
            test_name=test.full_name
        )
        known_issue.save()
        known_issue.environments.add(test_run.environment)
        self.assertEqual(1, len(KnownIssue.active_by_project_and_test(self.project, test.full_name)))

    def test_inactive_by_project(self):
        build = self.project.builds.create(
            datetime=self.date,
            version=self.date.strftime("%Y%m%d"),
        )
        test_run = build.test_runs.create(environment=self.env1)
        # create failed test
        foo_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite1.slug, name='test_foo', kind='test')
        test = test_run.tests.create(build=test_run.build, environment=test_run.environment, suite=self.suite1, metadata=foo_metadata, result=False)
        known_issue = KnownIssue.objects.create(
            title="foo",
            test_name=test.full_name
        )
        known_issue.save()
        known_issue.environments.add(test_run.environment)
        known_issue.active = False
        known_issue.save()

        self.assertEqual(0, len(KnownIssue.active_by_project_and_test(self.project, test.full_name)))

    def test_pattern_as_test_name(self):
        build = self.project.builds.create(
            datetime=self.date,
            version=self.date.strftime("%Y%m%d"),
        )
        testrun = build.test_runs.create(environment=self.env1)

        known_issue = KnownIssue.objects.create(
            title="foo",
            test_name="suite*/foo"
        )
        known_issue.save()
        known_issue.environments.add(testrun.environment)
        known_issue.save()

        tests_file = '{"suite1/foo": "pass", "suite2/foo": "pass", "notinpattern/foo": "pass"}'
        testrun.save_tests_file(tests_file)

        ParseTestRunData()(testrun)
        self.assertEqual(3, testrun.tests.count())

        for test in testrun.tests.filter(suite__slug__in="suite1,suite2").all():
            self.assertTrue(test.has_known_issues)
            self.assertIn(known_issue, test.known_issues.all())
