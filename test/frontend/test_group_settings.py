from django.test import TestCase
from django.test import Client

from squad.core import models


class TestNewGroup(TestCase):

    def setUp(self):
        self.user = models.User.objects.create(username='theuser')
        self.client = Client()
        self.client.force_login(self.user)

    def test_create_group(self):
        response = self.client.post('/_/new-group/', {'slug': 'mygroup'})
        self.assertEqual(302, response.status_code)
        self.assertTrue(models.Group.objects.filter(slug='mygroup').exists())

    def test_create_group_validates_uniqueness(self):
        models.Group.objects.create(slug='mygroup')
        response = self.client.post('/_/new-group/', {'slug': 'mygroup'})
        self.assertEqual(200, response.status_code)
        self.assertIn('already exists', str(response.content))


class TestNewProject(TestCase):

    def setUp(self):
        self.group = models.Group.objects.create(slug='mygroup')
        self.user = models.User.objects.create(username='theuser')
        self.group.add_admin(self.user)
        self.client = Client()
        self.client.force_login(self.user)

    def test_create_project(self):
        response = self.client.post(
            '/_/group-settings/mygroup/new-project/',
            {
                'slug': 'myproject'
            }
        )
        self.assertEqual(302, response.status_code)
        self.assertTrue(self.group.projects.filter(slug='myproject').exists())

    def test_create_group_validates_uniqueness(self):
        self.group.projects.create(slug='myproject')
        response = self.client.post(
            '/_/group-settings/mygroup/new-project/',
            {
                'slug': 'myproject'
            }
        )
        self.assertEqual(200, response.status_code)
        self.assertIn('already exists', str(response.content))
