import datetime
from unittest.mock import patch, MagicMock, call, PropertyMock
from celery.exceptions import Retry
from django.test import TestCase
from django.utils import timezone


from squad.core.models import Group, ProjectStatus, PatchSource
from squad.core.tasks.notification import maybe_notify_project_status
from squad.core.tasks.notification import notify_project_status
from squad.core.tasks.notification import notification_timeout
from squad.core.tasks.notification import notify_patch_build_created
from squad.core.tasks.notification import notify_patch_build_finished


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
