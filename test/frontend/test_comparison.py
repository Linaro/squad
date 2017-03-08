import json

from django.test import TestCase
from django.test import Client

from squad.core import models
from squad.core.tasks import ReceiveTestRun


class ProjectComparisonTest(TestCase):
    def receive_test_run(self, project, version, env, tests):
        receive = ReceiveTestRun(project)
        receive(version, env, tests_file=json.dumps(tests))

    def setUp(self):
        self.client = Client()

        self.group = models.Group.objects.create(slug='mygroup')
        self.project1 = self.group.projects.create(slug='project1')
        self.project2 = self.group.projects.create(slug='project2')

        self.receive_test_run(self.project1, '1', 'myenv', {
            'a': 'pass',
            'b': 'pass',
        })
        self.receive_test_run(self.project1, '1', 'myenv', {
            'c': 'fail',
            'd/e': 'pass',
        })
        self.receive_test_run(self.project2, '1', 'myenv', {
            'a': 'fail',
            'b': 'pass',
        })
        self.receive_test_run(self.project2, '1', 'myenv', {
            'c': 'pass',
            'd/e': 'pass',
        })

        self.receive_test_run(self.project1, '1', 'otherenv', {
            'a': 'pass',
            'b': 'pass',
        })
        self.receive_test_run(self.project1, '1', 'otherenv', {
            'c': 'fail',
            'd/e': 'pass',
        })
        self.receive_test_run(self.project2, '1', 'otherenv', {
            'a': 'fail',
            'b': 'pass',
        })
        self.receive_test_run(self.project2, '1', 'otherenv', {
            'c': 'pass',
            'd/e': 'pass',
        })

        self.build1 = self.project1.builds.last()
        self.build2 = self.project2.builds.last()

    def test_comparison_project_sanity_check(self):
        response = self.client.get('/_/compare/?project=mygroup/project1&project=mygroup/project2')
        self.assertEqual(200, response.status_code)
        self.assertIn('d/e', str(response.content))
        self.assertIn('myenv', str(response.content))
        self.assertIn('otherenv', str(response.content))
        self.assertIn('pass', str(response.content))
        self.assertIn('fail', str(response.content))
