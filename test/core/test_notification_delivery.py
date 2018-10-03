from django.test import TestCase


from squad.core.models import Group, ProjectStatus, NotificationDelivery


class NotificationDeliveryTest(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
        build1 = project.builds.create(version='1')
        self.status = ProjectStatus.create_or_update(build1)

    def test_avoid_duplicates(self):
        args = [self.status, 'my subject', 'text', 'html']
        self.assertFalse(NotificationDelivery.exists(*args))
        self.assertTrue(NotificationDelivery.exists(*args))

    def test_pass_modified_notifications(self):
        args = [self.status, 'my subject', 'text', 'html']
        self.assertFalse(NotificationDelivery.exists(*args))
        args[2] = 'new text'
        args[3] = 'new html'
        self.assertFalse(NotificationDelivery.exists(*args))
