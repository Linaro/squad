from unittest.mock import patch, MagicMock, call
from celery.exceptions import Retry
from django.test import TestCase
from django.utils import timezone


from squad.core.models import Group, ProjectStatus
from squad.core.tasks.notification import notify_project_status


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

    @patch('squad.core.tasks.notification.notify_project_status.retry')
    def test_retry_if_project_status_does_not_exist(self, retry):
        retry.return_value = Retry()

        with self.assertRaises(Retry):
            notify_project_status(666)
