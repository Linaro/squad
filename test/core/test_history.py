import json
from django.test import TestCase
from dateutil.relativedelta import relativedelta
from django.utils import timezone


from squad.core.tasks import ReceiveTestRun
from squad.core import models
from squad.core.history import TestHistory


class TestHistoryTest(TestCase):

    def receive_test_run(self, project, version, env, tests):
        receive = ReceiveTestRun(project, update_project_status=False)
        receive(version, env, tests_file=json.dumps(tests))

    def setUp(self):
        self.group = models.Group.objects.create(slug='mygruop')
        self.project1 = self.group.projects.create(slug='project1')

        self.receive_test_run(self.project1, '0', 'env1', {
            'foo/bar': 'fail',
            # missing `root` on purpose
        })

        now = timezone.now()
        past = now - relativedelta(hours=1)
        self.project1.builds.create(version='1', datetime=past)

        self.receive_test_run(self.project1, '1', 'env1', {
            'foo/bar': 'fail',
            'root': 'fail',
        })
        self.receive_test_run(self.project1, '1', 'env2', {
            'foo/bar': 'pass',
            'root': 'pass',
        })

        self.project1.builds.create(version='2', datetime=now)

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

    def test_pin_top_build(self):
        build1 = self.project1.builds.get(version='1')
        build2 = self.project1.builds.get(version='2')

        history = TestHistory(self.project1, 'root', top=build1)
        self.assertIn(build1, history.results.keys())
        self.assertNotIn(build2, history.results.keys())

        self.assertEqual(build1, history.top)

    def test_no_metadata(self):
        testrun = self.project1.builds.last().test_runs.last()
        suite = testrun.tests.last().suite
        test_name = 'no_metadata_test'
        metadata = models.SuiteMetadata.objects.create(kind='test', suite=suite.slug, name=test_name)
        testrun.tests.create(result=False, suite=suite, metadata=metadata, build=testrun.build, environment=testrun.environment)
        history = TestHistory(self.project1, test_name)

        self.assertIsNotNone(history.results)
