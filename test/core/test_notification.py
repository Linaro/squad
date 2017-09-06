from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core import mail
from django.utils import timezone
from django.test import TestCase
from unittest.mock import patch, MagicMock, PropertyMock


from squad.core.models import Group, Project, Build, ProjectStatus, EmailTemplate
from squad.core.notification import Notification, send_status_notification


class NotificationTest(TestCase):

    @patch("squad.core.comparison.TestComparison.diff", new_callable=PropertyMock)
    def test_delegates_diff_to_test_comparison_object(self, diff):
        the_diff = {}
        diff.return_value = the_diff

        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
        build1 = project.builds.create(version='1')
        ProjectStatus.create_or_update(build1)
        build2 = project.builds.create(version='2')
        status = ProjectStatus.create_or_update(build2)

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


class TestSendNotificationFirstTime(TestCase):
    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        self.project = group.projects.create(slug='myproject')
        t0 = timezone.now() - relativedelta(hours=3)
        self.build = self.project.builds.create(version='1', datetime=t0)
        self.project.subscriptions.create(email='foo@example.com')

    def test_send_if_notifying_all_builds(self):
        status = ProjectStatus.create_or_update(self.build)
        send_status_notification(status)
        self.assertEqual(1, len(mail.outbox))

    def test_dont_send_if_notifying_on_change(self):
        self.project.notification_strategy = Project.NOTIFY_ON_CHANGE
        self.project.save()
        status = ProjectStatus.create_or_update(self.build)
        send_status_notification(status)
        self.assertEqual(0, len(mail.outbox))


class TestSendNotification(TestCase):

    def setUp(self):
        t0 = timezone.now() - relativedelta(hours=3)
        t = timezone.now() - relativedelta(hours=2.75)

        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.build1 = self.project.builds.create(version='1', datetime=t0)
        status = ProjectStatus.create_or_update(self.build1)
        status.notified = True
        status.save()
        self.build2 = self.project.builds.create(version='2', datetime=t)

    @patch("squad.core.comparison.TestComparison.diff", new_callable=PropertyMock)
    def test_send_notification(self, diff):
        self.project.subscriptions.create(email='foo@example.com')
        diff.return_value = fake_diff()
        status = ProjectStatus.create_or_update(self.build2)
        send_status_notification(status)
        self.assertEqual(1, len(mail.outbox))

    @patch("squad.core.comparison.TestComparison.diff", new_callable=PropertyMock)
    def test_send_notification_for_all_builds(self, diff):
        self.project.subscriptions.create(email='foo@example.com')
        diff.return_value = fake_diff()

        status1 = ProjectStatus.create_or_update(self.build2)
        send_status_notification(status1)
        self.assertEqual(1, len(mail.outbox))

        t = timezone.now() - relativedelta(hours=2.5)
        build = self.project.builds.create(version='3', datetime=t)
        status2 = ProjectStatus.create_or_update(build)
        send_status_notification(status2)

        self.assertEqual(2, len(mail.outbox))

    def test_send_notification_on_change_only_with_no_changes(self):
        self.project.notification_strategy = Project.NOTIFY_ON_CHANGE
        self.project.save()
        self.project.subscriptions.create(email='foo@example.com')
        status = ProjectStatus.create_or_update(self.build2)
        send_status_notification(status)
        self.assertEqual(0, len(mail.outbox))

    @patch("squad.core.comparison.TestComparison.diff", new_callable=PropertyMock)
    def test_send_notification_on_change_only(self, diff):
        diff.return_value = fake_diff()
        self.project.notification_strategy = Project.NOTIFY_ON_CHANGE
        self.project.save()
        self.project.subscriptions.create(email='foo@example.com')
        status = ProjectStatus.create_or_update(self.build2)
        send_status_notification(status)
        self.assertEqual(1, len(mail.outbox))

    @patch("squad.core.comparison.TestComparison.diff", new_callable=PropertyMock)
    def test_no_recipients_no_email(self, diff):
        diff.return_value = fake_diff()
        status = ProjectStatus.create_or_update(self.build2)
        send_status_notification(status)
        self.assertEqual(0, len(mail.outbox))

    def test_send_a_single_notification_email(self):
        self.project.subscriptions.create(email='foo@example.com')
        self.project.subscriptions.create(email='bar@example.com')
        status = ProjectStatus.create_or_update(self.build2)
        send_status_notification(status)
        self.assertEqual(1, len(mail.outbox))

    def test_send_plain_text_only(self):
        self.project.subscriptions.create(email='foo@example.com')
        self.project.html_mail = False
        self.project.save()
        status = ProjectStatus.create_or_update(self.build2)

        send_status_notification(status)
        msg = mail.outbox[0]
        self.assertEqual(0, len(msg.alternatives))


class TestModeratedNotifications(TestCase):

    def setUp(self):
        t0 = timezone.now() - relativedelta(hours=3)
        t = timezone.now() - relativedelta(hours=2.75)

        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.build1 = self.project.builds.create(version='1', datetime=t0)
        status = ProjectStatus.create_or_update(self.build1)
        status.notified = True
        status.save()
        self.build2 = self.project.builds.create(version='2', datetime=t)
        self.project.subscriptions.create(email='user@example.com')
        self.project.admin_subscriptions.create(email='admin@example.com')
        self.project.moderate_notifications = True
        self.project.save()
        self.status = ProjectStatus.create_or_update(self.build2)


class TestSendUnmoderatedNotification(TestModeratedNotifications):

    def setUp(self):
        super(TestSendUnmoderatedNotification, self).setUp()
        send_status_notification(self.status)

    def test_mails_admins(self):
        self.assertEqual(['admin@example.com'], mail.outbox[0].recipients())

    def test_subject(self):
        self.assertTrue(mail.outbox[0].subject.startswith("[PREVIEW]"))

    def test_txt_banner(self):
        txt = mail.outbox[0].body
        self.assertTrue(txt.find('needs to be approved') >= 0)

    def test_html_banner(self):
        html = mail.outbox[0].alternatives[0][0]
        self.assertTrue(html.find('needs to be approved') >= 0)

    def test_does_not_mark_as_notified(self):
        self.assertFalse(self.status.notified)


class TestSendApprovedNotification(TestModeratedNotifications):

    def setUp(self):
        super(TestSendApprovedNotification, self).setUp()
        self.status.approved = True
        self.status.save()
        send_status_notification(self.status)

    def test_mails_users(self):
        self.assertEqual(['user@example.com'], mail.outbox[0].recipients())

    def test_marks_as_notified(self):
        self.assertTrue(self.status.notified)


class TestCustomEmailTemplate(TestCase):

    def setUp(self):
        t0 = timezone.now() - relativedelta(hours=3)
        t = timezone.now() - relativedelta(hours=2.75)

        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.build1 = self.project.builds.create(version='1', datetime=t0)
        status = ProjectStatus.create_or_update(self.build1)
        status.notified = True
        status.save()
        self.build2 = self.project.builds.create(version='2', datetime=t)
        self.project.subscriptions.create(email='user@example.com')
        self.project.admin_subscriptions.create(email='admin@example.com')

    def test_custom_template(self):
        template = EmailTemplate.objects.create(plain_text='foo', html='bar')
        self.project.use_custom_email_template = True
        self.project.custom_email_template = template
        self.project.save()

        status = ProjectStatus.create_or_update(self.build2)
        send_status_notification(status)

        msg = mail.outbox[0]
        txt = msg.body
        html = msg.alternatives[0][0]

        self.assertEqual('foo', txt)
        self.assertEqual('bar', html)

    def test_subject_from_custom_template(self):
        template = EmailTemplate.objects.create(subject='lalala', plain_text='foo', html='bar')
        self.project.use_custom_email_template = True
        self.project.custom_email_template = template
        self.project.save()

        status = ProjectStatus.create_or_update(self.build2)
        send_status_notification(status)

        msg = mail.outbox[0]
        self.assertEqual('lalala', msg.subject)
