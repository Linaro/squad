from django.test import TestCase
from django.utils import timezone

from squad.core.models import Group, KnownIssue


class KnownIssueTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.env1 = self.project.environments.create(slug='env1')
        self.suite1 = self.project.suites.create(slug="suite1")
        self.date = timezone.now()

    def test_active_known_issue(self):
        build = self.project.builds.create(
            datetime=self.date,
            version=self.date.strftime("%Y%m%d"),
        )
        test_run = build.test_runs.create(environment=self.env1)
        # create failed test
        test = test_run.tests.create(suite=self.suite1, name="test_foo", result=False)
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
        test = test_run.tests.create(suite=self.suite1, name="test_foo", result=False)
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
        test = test_run.tests.create(suite=self.suite1, name="test_foo", result=False)
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
        test = test_run.tests.create(suite=self.suite1, name="test_foo", result=False)
        known_issue = KnownIssue.objects.create(
            title="foo",
            test_name=test.full_name
        )
        known_issue.save()
        known_issue.environments.add(test_run.environment)
        known_issue.active = False
        known_issue.save()

        self.assertEqual(0, len(KnownIssue.active_by_project_and_test(self.project, test.full_name)))
