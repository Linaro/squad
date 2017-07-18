from unittest.mock import patch, MagicMock, call
from django.test import TestCase


from squad.core.models import Group
from squad.core.tasks.notification import notify_project


class TestNotificationTasks(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        self.project1 = group.projects.create(slug='myproject1')
        self.project2 = group.projects.create(slug='myproject2')

    @patch("squad.core.tasks.notification.send_notification")
    def test_notify_project(self, send_notification):
        notify_project.apply(args=[self.project1.id])
        send_notification.assert_called_with(self.project1)
