from django.test import Client
from django.test import TestCase
from squad.core.models import Group


class TestHistoryTest(TestCase):

    def setUp(self):
        self.client = Client()
        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
        env = project.environments.create(slug='myenv')
        suite = project.suites.create(slug='mysuite')
        build = project.builds.create(version='mybuild')
        self.testrun = build.test_runs.create(job_id='123', environment=env)
        self.testrun.tests.create(name='mytest', suite=suite)
        self.testrun.status.create(test_run=self.testrun, suite=suite)

    def test_tests_history_with_empty_suite_metadata(self):
        response = self.client.get('/mygroup/myproject/build/mybuild/testrun/%s/suite/mysuite/test/mytest/history/' % self.testrun.id)
        self.assertEqual(200, response.status_code)
