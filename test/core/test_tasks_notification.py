from unittest.mock import patch, MagicMock, call
from django.test import TestCase


from squad.core.models import Group
from squad.core.tasks.notification import notify_project, notify_all_projects


class TestNotificationTasks(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        self.project1 = group.projects.create(slug='myproject1')
        self.project2 = group.projects.create(slug='myproject2')

    @patch("squad.core.tasks.notification.send_notification")
    def test_notify_project(self, send_notification):
        notify_project.apply(args=[self.project1.id])
        send_notification.assert_called_with(self.project1)

    @patch("squad.core.tasks.notification.notify_project.delay")
    def test_notify_all_projects(self, notify_project):
        notify_all_projects.apply()
        notify_project.assert_has_calls([
            call(self.project1.id),
            call(self.project2.id),
        ])
