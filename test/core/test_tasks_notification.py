import datetime
import time
import threading
from unittest.mock import patch, MagicMock
from django.db import connection
from django.test import TestCase, TransactionTestCase, tag
from django.utils import timezone


from squad.core.models import Group, ProjectStatus, PatchSource, DelayedReport
from squad.core.tasks.notification import maybe_notify_project_status
from squad.core.tasks.notification import notify_project_status
from squad.core.tasks.notification import notification_timeout
from squad.core.tasks.notification import notify_patch_build_created
from squad.core.tasks.notification import notify_patch_build_finished
from squad.core.tasks.notification import notify_delayed_report_callback
from squad.core.tasks.notification import notify_delayed_report_email


class TestNotificationTasks(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        self.project1 = group.projects.create(slug='myproject1')
        self.project2 = group.projects.create(slug='myproject2')

    @patch("squad.core.tasks.notification.send_status_notification")
    def test_notify_project_status(self, send_status_notification):
        build = self.project1.builds.create(datetime=timezone.now())
        environment = self.project1.environments.create(slug='env')
        build.test_runs.create(environment=environment)

        status = ProjectStatus.create_or_update(build)
        notify_project_status(status.id)

        send_status_notification.assert_called_with(status)

    @patch("squad.core.tasks.notification.send_status_notification")
    def test_maybe_notify_project_status(self, send_status_notification):
        build = self.project1.builds.create(datetime=timezone.now())
        environment = self.project1.environments.create(slug='env')
        build.test_runs.create(environment=environment)
        status = ProjectStatus.create_or_update(build)

        maybe_notify_project_status(status.id)
        send_status_notification.assert_called_with(status)

    @patch("squad.core.tasks.notification.notify_patch_build_finished")
    def test_maybe_notify_project_status_notify_patch_build_finished(self, notify_patch_build_finished):
        build = self.project1.builds.create(datetime=timezone.now())
        environment = self.project1.environments.create(slug='env')
        build.test_runs.create(environment=environment)
        status = ProjectStatus.create_or_update(build)

        maybe_notify_project_status(status.id)
        notify_patch_build_finished.delay.assert_called_with(build.id)

    @patch("squad.core.tasks.notification.send_status_notification")
    def test_maybe_notify_project_status_do_not_send_dup_notification(self, send_status_notification):
        build = self.project1.builds.create(datetime=timezone.now())
        environment = self.project1.environments.create(slug='env')
        build.test_runs.create(environment=environment)
        status = ProjectStatus.create_or_update(build)

        status.notified = True
        status.save()

        maybe_notify_project_status(status.id)
        send_status_notification.assert_not_called()

    @patch("django.utils.timezone.now")
    @patch("squad.core.tasks.notification.send_status_notification")
    @patch("squad.core.tasks.notification.maybe_notify_project_status.apply_async")
    def test_maybe_notify_project_status_wait_before_notification(self, apply_async, send_status_notification, now):
        self.project1.wait_before_notification = 3600  # 1 hour
        self.project1.save()

        # build was created half an hour ago
        now.return_value = timezone.make_aware(datetime.datetime(2017, 10, 20, 10, 30, 0))
        build = self.project1.builds.create(datetime=timezone.make_aware(datetime.datetime(2017, 10, 20, 10, 0, 0)))
        environment = self.project1.environments.create(slug='env')
        build.test_runs.create(environment=environment)
        status = ProjectStatus.create_or_update(build)

        maybe_notify_project_status(status.id)

        send_status_notification.assert_not_called()
        apply_async.assert_called_with(args=[status.id], countdown=1801)

    @patch("django.utils.timezone.now")
    @patch("squad.core.tasks.notification.send_status_notification")
    @patch("squad.core.tasks.notification.maybe_notify_project_status.apply_async")
    def test_maybe_notify_project_status_notifies_after_wait_before_notification(self, apply_async, send_status_notification, now):
        self.project1.wait_before_notification = 3600  # 1 hour
        self.project1.save()

        # build was created more than one hour ago
        now.return_value = timezone.make_aware(datetime.datetime(2017, 10, 20, 10, 30, 0))
        build = self.project1.builds.create(datetime=timezone.make_aware(datetime.datetime(2017, 10, 20, 9, 0, 0)))
        environment = self.project1.environments.create(slug='env')
        build.test_runs.create(environment=environment)
        status = ProjectStatus.create_or_update(build)

        maybe_notify_project_status(status.id)

        send_status_notification.assert_called_with(status)
        apply_async.assert_not_called()

    @patch("squad.core.tasks.notification.notification_timeout.apply_async")
    def test_maybe_notify_project_status_schedule_timeout(self, apply_async):
        self.project1.notification_timeout = 3600  # 1 hour
        self.project1.save()

        build = self.project1.builds.create(datetime=timezone.now())
        environment = self.project1.environments.create(slug='env')
        build.test_runs.create(environment=environment)
        status = ProjectStatus.create_or_update(build)

        maybe_notify_project_status(status.id)
        apply_async.assert_called_with(args=[status.id], countdown=3600)

    @patch("squad.core.tasks.notification.notification_timeout.apply_async")
    def test_maybe_notify_project_status_schedule_timeout_not_requested(self, apply_async):
        build = self.project1.builds.create(datetime=timezone.now())
        environment = self.project1.environments.create(slug='env')
        build.test_runs.create(environment=environment)
        status = ProjectStatus.create_or_update(build)

        maybe_notify_project_status(status.id)
        apply_async.assert_not_called()

    @patch("squad.core.tasks.notification.send_status_notification")
    def test_notification_timeout(self, send_status_notification):
        self.project1.notification_timeout = 3600  # 1 hour
        self.project1.save()

        build = self.project1.builds.create(datetime=timezone.now())
        environment = self.project1.environments.create(slug='env')
        build.test_runs.create(environment=environment)
        status = ProjectStatus.create_or_update(build)

        notification_timeout(status.id)
        send_status_notification.assert_called_with(status)

    @patch("squad.core.tasks.notification.send_status_notification")
    def test_notification_timeout_noop(self, send_status_notification):
        self.project1.notification_timeout = 3600  # 1 hour
        self.project1.save()

        build = self.project1.builds.create(datetime=timezone.now())
        environment = self.project1.environments.create(slug='env')
        build.test_runs.create(environment=environment)
        status = ProjectStatus.create_or_update(build)
        status.notified = True
        status.save()

        notification_timeout(status.id)
        send_status_notification.assert_not_called()

    @patch("squad.core.tasks.notification.send_status_notification")
    def test_notification_timeout_only_once(self, send_status_notification):
        self.project1.notification_timeout = 3600  # 1 hour
        self.project1.save()

        build = self.project1.builds.create(datetime=timezone.now())
        environment = self.project1.environments.create(slug='env')
        build.test_runs.create(environment=environment)
        status = ProjectStatus.create_or_update(build)

        notification_timeout(status.id)
        notification_timeout(status.id)
        self.assertEqual(1, len(send_status_notification.call_args_list))

    @patch("squad.core.tasks.notification.notification_timeout.apply_async")
    def test_notification_timeout_only_one_task(self, notification_timeout_apply_async):
        self.project1.notification_timeout = 3600  # 1 hour
        self.project1.save()

        build = self.project1.builds.create(datetime=timezone.now())
        environment = self.project1.environments.create(slug='env')
        build.test_runs.create(environment=environment)
        status = ProjectStatus.create_or_update(build)

        maybe_notify_project_status(status.id)
        maybe_notify_project_status(status.id)
        self.assertEqual(1, len(notification_timeout_apply_async.call_args_list))


# https://stackoverflow.com/a/10949616/3908350
class TestNotificationTasksRaceCondition(TransactionTestCase):

    def mock_apply_async(args, countdown=None):
        time.sleep(1)

    @tag('skip_sqlite')
    @patch("squad.core.tasks.notification.notification_timeout.apply_async", side_effect=mock_apply_async)
    def test_notification_race_condition(self, notification_timeout_apply_async):
        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject1', notification_timeout=1)
        build = project.builds.create(datetime=timezone.now())
        status = ProjectStatus.create_or_update(build)

        # ref: https://stackoverflow.com/a/56584761/3908350
        def thread(status_id):
            maybe_notify_project_status(status_id)
            connection.close()

        parallel_task_1 = threading.Thread(target=thread, args=(status.id,))
        parallel_task_2 = threading.Thread(target=thread, args=(status.id,))

        parallel_task_1.start()
        parallel_task_2.start()

        parallel_task_1.join()
        parallel_task_2.join()

        self.assertEqual(1, notification_timeout_apply_async.call_count)


class TestPatchNotificationTasks(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        self.project = group.projects.create(slug='myproject')
        self.patch_source = PatchSource.objects.create(
            name='foo',
            implementation='example',
        )

    @patch("squad.core.models.PatchSource.get_implementation")
    def test_notify_patch_build_created(self, get_implementation):
        build = self.project.builds.create(
            version='1',
            patch_source=self.patch_source,
            patch_id='0123456789',
        )

        plugin = MagicMock()
        get_implementation.return_value = plugin

        notify_patch_build_created(build.id)
        plugin.notify_patch_build_created.assert_called_with(build)

    @patch("squad.core.models.PatchSource.get_implementation")
    def test_notify_patch_build_finished(self, get_implementation):
        build = self.project.builds.create(
            version='1',
            patch_source=self.patch_source,
            patch_id='0123456789',
        )

        plugin = MagicMock()
        get_implementation.return_value = plugin

        notify_patch_build_finished(build.id)
        plugin.notify_patch_build_finished.assert_called_with(build)


class TestReportNotificationTasks(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.build = self.project.builds.create(version='1')
        self.report = self.build.delayed_reports.create()

    @patch('requests.Session')
    def test_callback_notification(self, send_mock):
        url = "https://foo.bar.com"
        self.report.callback = url
        self.report.save()
        notify_delayed_report_callback(self.report.pk)
        send_mock.assert_any_call()
        report = DelayedReport.objects.get(pk=self.report.pk)
        self.assertTrue(report.callback_notified)

    @patch('requests.Session.send')
    def test_callback_notification_sent_earlier(self, send_mock):
        self.report.callback = "https://foo.bar.com"
        self.report.callback_notified = True
        self.report.save()
        notify_delayed_report_callback(self.report.pk)
        send_mock.assert_not_called()

    @patch('squad.core.models.DelayedReport.send')
    def test_email_notification(self, send_mock):
        self.report.email_recipient = "foo@bar.com"
        self.report.save()
        notify_delayed_report_email(self.report.pk)
        send_mock.assert_called_with()

    @patch('squad.core.models.DelayedReport.send')
    def test_email_notification_sent_earlier(self, send_mock):
        self.report.email_recipient = "foo@bar.com"
        self.report.email_recipient_notified = True
        self.report.save()
        notify_delayed_report_email(self.report.pk)
        send_mock.assert_not_called()
