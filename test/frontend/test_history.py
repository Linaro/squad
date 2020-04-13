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


class TestHistoryTest(TestCase):

    def setUp(self):
        self.client = Client()
        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
        env = project.environments.create(slug='myenv')
        suite = project.suites.create(slug='mysuite')
        build = project.builds.create(version='mybuild')
        testrun = build.test_runs.create(job_id='123', environment=env)
        testrun.tests.create(name='mytest', suite=suite)

    def test_tests_history_with_empty_suite_metadata(self):
        response = self.client.get('/mygroup/myproject/tests/mysuite/mytest')
        self.assertEqual(200, response.status_code)
