import json


from django.test import TestCase


from squad.core import models
from squad.core.comparison import TestComparison
from squad.core.tasks import ReceiveTestRun


def compare(b1, b2):
    return TestComparison.compare_builds(b1, b2)


class TestComparisonTest(TestCase):

    def receive_test_run(self, project, version, env, tests):
        receive = ReceiveTestRun(project)
        receive(version, env, tests_file=json.dumps(tests))

    def setUp(self):
        self.group = models.Group.objects.create(slug='mygruop')
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

    def test_builds(self):
        comp = compare(self.build1, self.build2)
        self.assertEqual([self.build1, self.build2], comp.builds)

    def test_test_runs(self):
        comp = compare(self.build1, self.build2)

        environments = list(self.project1.environments.all()) + list(self.project2.environments.all())
        myenv1, otherenv1, myenv2, otherenv2 = environments  # order of creation

        self.assertEqual([myenv1, otherenv1], comp.environments[self.build1])
        self.assertEqual([myenv2, otherenv2], comp.environments[self.build2])

    def test_tests(self):
        comp = compare(self.build1, self.build2)
        self.assertEqual(['a', 'b', 'c', 'd/e'], sorted(comp.results.keys()))

    def test_test_results(self):
        comp = compare(self.build1, self.build2)

        env1 = self.project1.builds.last().test_runs.last().environment
        env2 = self.project2.builds.last().test_runs.last().environment

        self.assertEqual('pass', comp.results['a'][env1])
        self.assertEqual('fail', comp.results['c'][env1])

        self.assertEqual('fail', comp.results['a'][env2])
        self.assertEqual('pass', comp.results['b'][env2])

    def test_compare_projects(self):
        comp = TestComparison.compare_projects(self.project1, self.project2)
        self.assertEqual([self.build1, self.build2], comp.builds)

    def test_no_data(self):
        new_project = self.group.projects.create(slug='new')
        TestComparison.compare_projects(new_project)
