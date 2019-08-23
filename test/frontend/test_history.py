from django.test import Client
from django.test import TestCase
from squad.core.models import Group


class TestHistoryWithNoData(TestCase):

    def setUp(self):
        self.client = Client()
        group = Group.objects.create(slug='mygroup')
        group.projects.create(slug='myproject')

    def test_history_without_full_test_name(self):
        response = self.client.get('/mygroup/myproject/tests/')
        self.assertEqual(404, response.status_code)

    def test_history_without_suite_name(self):
        response = self.client.get('/mygroup/myproject/tests/foo')
        self.assertEqual(404, response.status_code)

    def test_history_with_unexisting_suite_name(self):
        response = self.client.get('/mygroup/myproject/tests/foo/bar')
        self.assertEqual(404, response.status_code)
