from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core import mail
from django.utils import timezone
from django.test import TestCase
from unittest.mock import patch, MagicMock, PropertyMock


from squad.core.models import Group, Project, Build, ProjectStatus
from squad.core.notification import Notification, send_notification


class NotificationTest(TestCase):

    @patch("squad.core.comparison.TestComparison.diff", new_callable=PropertyMock)
    def test_delegates_diff_to_test_comparison_object(self, diff):
        the_diff = {}
        diff.return_value = the_diff

        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
        build1 = project.builds.create(version='1')
        build2 = project.builds.create(version='2')

        notification = Notification(build2, build1)

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


class TestSendNotificationFirstTime(TestCase):
    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        self.project = group.projects.create(slug='myproject')
        t0 = timezone.now() - relativedelta(hours=3)
        self.project.builds.create(version='1', datetime=t0)
        self.project.subscriptions.create(email='foo@example.com')

    def test_send_if_notifying_all_builds(self):
        send_notification(self.project)
        self.assertEqual(1, len(mail.outbox))

    def test_dont_send_if_notifying_on_change(self):
        self.project.notification_strategy = Project.NOTIFY_ON_CHANGE
        self.project.save()
        send_notification(self.project)
        self.assertEqual(0, len(mail.outbox))


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
    def test_send_notification_for_all_builds(self, diff):
        t = timezone.now() - relativedelta(hours=2.5)
        self.project.builds.create(version='3', datetime=t)
        self.project.subscriptions.create(email='foo@example.com')
        diff.return_value = fake_diff()
        send_notification(self.project)
        self.assertEqual(2, len(mail.outbox))

    def test_send_notification_on_change_only_with_no_changes(self):
        self.project.notification_strategy = Project.NOTIFY_ON_CHANGE
        self.project.save()
        self.project.subscriptions.create(email='foo@example.com')
        send_notification(self.project)
        self.assertEqual(0, len(mail.outbox))

    @patch("squad.core.comparison.TestComparison.diff", new_callable=PropertyMock)
    def test_send_notification_on_change_only(self, diff):
        diff.return_value = fake_diff()
        self.project.notification_strategy = Project.NOTIFY_ON_CHANGE
        self.project.save()
        self.project.subscriptions.create(email='foo@example.com')
        send_notification(self.project)
        self.assertEqual(1, len(mail.outbox))

    @patch("squad.core.comparison.TestComparison.diff", new_callable=PropertyMock)
    def test_no_recipients_no_email(self, diff):
        diff.return_value = fake_diff()
        send_notification(self.project)
        self.assertEqual(0, len(mail.outbox))

    def test_send_notification_without_html(self):
        self.project.subscriptions.create(email='foo@example.com', html=False)
        send_notification(self.project)
        message = mail.outbox[0]
        self.assertEqual(0, len(message.alternatives))
