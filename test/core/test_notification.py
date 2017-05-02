from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core import mail
from django.utils import timezone
from django.test import TestCase
from unittest.mock import patch, MagicMock, PropertyMock


from squad.core.models import Group, Build, ProjectStatus
from squad.core.notification import Notification, send_notification


class NotificationTest(TestCase):

    def test_does_not_send_on_first_project_status(self):
        status = ProjectStatus(build=Build())
        notification = Notification(status)
        self.assertFalse(notification.must_be_sent)

    @patch("squad.core.notification.Notification.diff", new_callable=PropertyMock, return_value={})
    def test_does_not_send_with_empty_diff(self, diff):
        status0 = ProjectStatus(build=Build())
        status = ProjectStatus(build=Build(), previous=status0)
        notification = Notification(status)

        self.assertFalse(notification.must_be_sent)

    @patch("squad.core.notification.Notification.diff", new_callable=PropertyMock, return_value={'a': {}})
    def test_sends_when_there_is_a_diff(self, diff):
        status0 = ProjectStatus(build=Build())
        status = ProjectStatus(build=Build(), previous=status0)
        notification = Notification(status)

        self.assertTrue(notification.must_be_sent)

    @patch("squad.core.comparison.TestComparison.diff", new_callable=PropertyMock)
    def test_delegates_diff_to_test_comparison_object(self, diff):
        the_diff = {}
        diff.return_value = the_diff

        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
        build1 = project.builds.create(version='1')
        build2 = project.builds.create(version='2')

        status1 = ProjectStatus(build=build1)
        status = ProjectStatus(build=build2, previous=status1)
        notification = Notification(status)

        self.assertIs(the_diff, notification.diff)


def fake_diff():
    build1 = MagicMock()
    build2 = MagicMock()
    env1 = MagicMock()
    env2 = MagicMock()
    return {
        'test1': {build1: {env1: True, env2: True}, build2: {env1: True, env2: False}},
        'test2': {build1: {env1: True, env2: True}, build2: {env1: True, env2: False}},
    }


class TestSendNotification(TestCase):

    def setUp(self):
        t0 = timezone.now() - relativedelta(hours=3)
        t = timezone.now() - relativedelta(hours=3)

        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.project.builds.create(version='1', datetime=t0)
        ProjectStatus.create(self.project)
        self.project.builds.create(version='2', datetime=t)

    @patch("squad.core.comparison.TestComparison.diff", new_callable=PropertyMock)
    def test_send_notification(self, diff):
        self.project.subscriptions.create(email='foo@example.com')
        diff.return_value = fake_diff()
        send_notification(self.project)
        self.assertEqual(1, len(mail.outbox))

    @patch("squad.core.comparison.TestComparison.diff", new_callable=PropertyMock)
    def test_no_recipients_no_email(self, diff):
        diff.return_value = fake_diff()
        send_notification(self.project)
        self.assertEqual(0, len(mail.outbox))
