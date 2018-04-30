import json
from django.test import TestCase


from squad.core.tasks import ReceiveTestRun
from squad.core import models
from squad.core.history import TestHistory


class TestHistoryTest(TestCase):

    def receive_test_run(self, project, version, env, tests):
        receive = ReceiveTestRun(project)
        receive(version, env, tests_file=json.dumps(tests))

    def setUp(self):
        self.group = models.Group.objects.create(slug='mygruop')
        self.project1 = self.group.projects.create(slug='project1')

        self.receive_test_run(self.project1, '0', 'env1', {
            'foo/bar': 'fail',
            # missing `root` on purpose
        })

        self.receive_test_run(self.project1, '1', 'env1', {
            'foo/bar': 'fail',
            'root': 'fail',
        })
        self.receive_test_run(self.project1, '1', 'env2', {
            'foo/bar': 'pass',
            'root': 'pass',
        })

        self.receive_test_run(self.project1, '2', 'env1', {
            'foo/bar': 'pass',
            'root': 'pass',
        })
        self.receive_test_run(self.project1, '2', 'env2', {
            'foo/bar': 'fail',
            'root': 'fail',
        })

    def test_environments(self):
        history = TestHistory(self.project1, 'foo/bar')
        env1 = self.project1.environments.get(slug='env1')
        env2 = self.project1.environments.get(slug='env2')
        self.assertEqual([env1.id, env2.id], sorted([e.id for e in history.environments]))

    def test_results(self):
        history = TestHistory(self.project1, 'foo/bar')

        build1 = self.project1.builds.get(version='1')
        build2 = self.project1.builds.get(version='2')
        env1 = self.project1.environments.get(slug='env1')
        env2 = self.project1.environments.get(slug='env2')

        self.assertEqual('fail', history.results[build1][env1].status)
        self.assertEqual('pass', history.results[build1][env2].status)
        self.assertEqual('pass', history.results[build2][env1].status)
        self.assertEqual('fail', history.results[build2][env2].status)

    def test_results_no_suite(self):
        history = TestHistory(self.project1, 'root')

        build1 = self.project1.builds.get(version='1')
        build2 = self.project1.builds.get(version='2')
        env1 = self.project1.environments.get(slug='env1')
        env2 = self.project1.environments.get(slug='env2')

        self.assertEqual('fail', history.results[build1][env1].status)
        self.assertEqual('pass', history.results[build1][env2].status)
        self.assertEqual('pass', history.results[build2][env1].status)
        self.assertEqual('fail', history.results[build2][env2].status)

    def test_displays_all_builds(self):
        build0 = self.project1.builds.get(version='0')
        history = TestHistory(self.project1, 'root')

        self.assertIn(build0, history.results)

    def test_pagination(self):
        build1 = self.project1.builds.get(version='1')
        build2 = self.project1.builds.get(version='2')

        history = TestHistory(self.project1, 'root', page=1, per_page=1)
        self.assertIn(build2, history.results.keys())
        self.assertNotIn(build1, history.results.keys())
