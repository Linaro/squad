import json


from math import sqrt


from django.test import TestCase


from squad.core import models
from squad.core.comparison import MetricComparison
from squad.core.tasks import ReceiveTestRun


def compare(b1, b2):
    return MetricComparison.compare_builds(b1, b2)


class MetricComparisonTest(TestCase):

    def receive_test_run(self, project, version, env, metrics):
        receive = ReceiveTestRun(project)
        receive(version, env, metrics_file=json.dumps(metrics))

    def setUp(self):
        self.group = models.Group.objects.create(slug='mygruop')
        self.project1 = self.group.projects.create(slug='project1')
        self.project2 = self.group.projects.create(slug='project2')

        self.receive_test_run(self.project1, '0', 'myenv', {
            'z': 0.1,
        })
        self.receive_test_run(self.project1, '0', 'myenv', {
            'z': 0.2,
        })
        self.receive_test_run(self.project2, '0', 'otherenv', {
            'z': 0.1,
        })

        self.receive_test_run(self.project1, '1', 'myenv', {
            'a': 0.2,
            'b': 0.3,
        })
        self.receive_test_run(self.project1, '1', 'myenv', {
            'c': 0.4,
            'd/e': 0.5,
        })
        self.receive_test_run(self.project2, '1', 'myenv', {
            'a': 0.2,
            'b': 0.3,
        })
        self.receive_test_run(self.project2, '1', 'myenv', {
            'c': 2.5,
            'd/e': 2.5,
        })

        self.receive_test_run(self.project1, '1', 'otherenv', {
            'a': 0.2,
            'b': 0.4,
        })
        self.receive_test_run(self.project1, '1', 'otherenv', {
            'c': 0.5,
            'd/e': 0.6,
        })
        self.receive_test_run(self.project2, '1', 'otherenv', {
            'a': 0.2,
            'b': 0.4,
        })
        self.receive_test_run(self.project2, '1', 'otherenv', {
            'c': 2.5,
            'd/e': 2.4,
        })

        self.build0 = self.project1.builds.first()
        self.build1 = self.project1.builds.last()
        self.build2 = self.project2.builds.first()
        self.build3 = self.project2.builds.last()

    def test_builds(self):
        comp = compare(self.build1, self.build3)
        self.assertEqual([self.build1, self.build3], comp.builds)

    def test_test_runs(self):
        comp = compare(self.build1, self.build3)

        self.assertEqual(['myenv', 'otherenv'], comp.environments[self.build1])
        self.assertEqual(['myenv', 'otherenv'], comp.environments[self.build3])

    def test_metrics_are_sorted(self):
        comp = compare(self.build0, self.build1)
        self.assertEqual(['a', 'b', 'c', 'd/e', 'z'], list(comp.results.keys()))

    def test_metric_results(self):
        comp = compare(self.build1, self.build3)

        self.assertEqual((0.2, 0.0, 1), comp.results['a'][self.build1, 'otherenv'])
        self.assertEqual((0.5, 0.0, 1), comp.results['c'][self.build1, 'otherenv'])

        self.assertEqual((0.2, 0.0, 1), comp.results['a'][self.build3, 'otherenv'])
        self.assertEqual((0.4, 0.0, 1), comp.results['b'][self.build3, 'otherenv'])

    def test_compare_projects(self):
        comp = MetricComparison.compare_projects(self.project1, self.project2)
        self.assertEqual([self.build1, self.build3], comp.builds)

    def test_no_data(self):
        new_project = self.group.projects.create(slug='new')
        comp = MetricComparison.compare_projects(new_project)
        self.assertFalse(comp.diff)
        self.assertEqual([], comp.builds)

    def test_diff(self):
        comparison = compare(self.build1, self.build3)
        diff = comparison.diff
        self.assertEqual(['c', 'd/e'], sorted(diff.keys()))

    def test_empty_diff(self):
        comparison = compare(self.build1, self.build1)  # same build → no diff
        self.assertFalse(comparison.diff)

    def test_empty_with_no_builds(self):
        new_project = self.group.projects.create(slug='new')
        comparison = MetricComparison.compare_projects(new_project)
        self.assertFalse(comparison.diff)

    def test_multiple_values_same_metric(self):
        comparison = compare(self.build0, self.build2)
        diff = comparison.diff
        self.assertEqual(['z'], sorted(diff.keys()))

        true_mean = (0.1 + 0.2) / 2.0  # mean
        true_stddev = sqrt((pow(0.1 - true_mean, 2.0) + pow(0.2 - true_mean, 2.0)) / 2.0)  # standard deviation
        mean, stddev, count = diff['z'][self.build0, 'myenv']
        self.assertAlmostEqual(true_mean, mean)
        self.assertAlmostEqual(true_stddev, stddev)
        self.assertEqual(2, count)
