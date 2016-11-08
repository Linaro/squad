from django.test import TestCase
from django.test import Client
from django.contrib.auth.models import User


from squad.core import models


class FrontendTest(TestCase):

    def setUp(self):
        self.group = models.Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.user = User.objects.create(username='theuser')

        self.client = Client()
        self.client.force_login(self.user)

    def hit(self, url):
        response = self.client.get('/')
        self.assertEqual(200, response.status_code)

    def test_home(self):
        self.hit('/')

    def test_group(self):
        self.hit('/mygroup')

    def test_project(self):
        self.hit('/mygroup/myproject')

    def test_builds(self):
        self.hit('/mygroup/myproject/builds')
