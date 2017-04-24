from django.test import TestCase
from unittest.mock import patch, MagicMock, PropertyMock


from squad.core.models import Group, Build, ProjectStatus
from squad.core.notification import Notification


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
