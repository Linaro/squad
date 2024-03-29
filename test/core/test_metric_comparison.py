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
        receive = ReceiveTestRun(project, update_project_status=False)
        receive(version, env, metrics_file=json.dumps(metrics))

    def setUp(self):
        self.group = models.Group.objects.create(slug='mygruop')
        self.project1 = self.group.projects.create(slug='project1')
        self.project2 = self.group.projects.create(slug='project2')

        self.receive_test_run(self.project1, '0', 'myenv', {
            'z': {"value": 0.1, "unit": ""}
        })
        self.receive_test_run(self.project1, '0', 'myenv', {
            'z': {"value": 0.2, "unit": "bikes"}
        })
        self.receive_test_run(self.project2, '0', 'otherenv', {
            'z': {"value": 0.1, "unit": "seconds"}

        })
        self.receive_test_run(self.project1, '1', 'myenv', {
            'a': {"value": 0.2, "unit": "seconds"},
            'b': {"value": 0.3, "unit": "seconds"}
        })
        self.receive_test_run(self.project1, '1', 'myenv', {
            'c': {"value": 0.4, "unit": "seconds"},
            'd/e': {"value": 0.5, "unit": "seconds"}
        })
        self.receive_test_run(self.project2, '1', 'myenv', {
            'a': {"value": 0.2, "unit": "seconds"},
            'b': {"value": 0.3, "unit": "seconds"}
        })
        self.receive_test_run(self.project2, '1', 'myenv', {
            'c': {"value": 2.5, "unit": "seconds"},
            'd/e': {"value": 2.5, "unit": "seconds"}
        })

        self.receive_test_run(self.project1, '1', 'otherenv', {
            'a': {"value": 0.2, "unit": "seconds"},
            'b': {"value": 0.4, "unit": "seconds"}
        })
        self.receive_test_run(self.project1, '1', 'otherenv', {
            'c': {"value": 0.5, "unit": "seconds"},
            'd/e': {"value": 0.6, "unit": "seconds"}
        })
        self.receive_test_run(self.project2, '1', 'otherenv', {
            'a': {"value": 0.2, "unit": "seconds"},
            'b': {"value": 0.4, "unit": "seconds"}
        })
        self.receive_test_run(self.project2, '1', 'otherenv', {
            'c': {"value": 2.5, "unit": "seconds"},
            'd/e': {"value": 2.4, "unit": "seconds"}
        })

        self.build0 = self.project1.builds.first()
        self.build1 = self.project1.builds.last()
        self.build2 = self.project2.builds.first()
        self.build3 = self.project2.builds.last()

        # Data for testing regressions and fixes
        self.project = self.group.projects.create(slug='project')
        self.environment_a = self.project.environments.create(slug='env_a')
        self.environment_b = self.project.environments.create(slug='env_b')
        self.build_a = self.project.builds.create(version='build_a')
        self.build_b = self.project.builds.create(version='build_b')

        # Create a few thresholds to trigger comparison
        self.project.thresholds.create(name='suite_a/regressing-metric-higher-better', is_higher_better=True)
        self.project.thresholds.create(name='suite_a/regressing-metric-lower-better', is_higher_better=False)
        self.project.thresholds.create(name='suite_a/improved-metric-higher-better', is_higher_better=True)
        self.project.thresholds.create(name='suite_a/improved-metric-lower-better', is_higher_better=False)
        self.project.thresholds.create(name='suite_a/stable-metric')

        # Thresholds with value WILL NOT trigger regressions/fixes
        self.project.thresholds.create(name='suite_a/valueness-threshold-metric', value=1)

        # Thresholds from different environments SHOULD NOT interact
        self.project.thresholds.create(name='suite_a/different-env-metric', environment=self.environment_a)
        self.project.thresholds.create(name='suite_a/different-env-metric', environment=self.environment_b)

        # Thresholds from different suites SHOULD NOT interact
        self.project.thresholds.create(name='suite_a/different-suite-metric')
        self.project.thresholds.create(name='suite_b/different-suite-metric')

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

    def test_basic(self):

        #   metric full name            | build1 result | build2 result | expected result
        # False -> the metric has regressed, True -> the metric has been fixed, None -> not a regression nor fix
        test_cases = {
            'suite_a/improved-metric-higher-better': (1, 2, True),
            'suite_a/improved-metric-lower-better': (2, 1, True),
            'suite_a/regressing-metric-higher-better': (2, 1, False),
            'suite_a/regressing-metric-lower-better': (1, 2, False),
            'suite_a/stable-metric': (1, 1, None),
            'suite_a/thresholdless-metric': (1, 2, None),
            'suite_a/valueness-threshold-metric': (1, 2, None),
        }

        for metric_name in test_cases.keys():
            build_a_result = test_cases[metric_name][0]
            build_b_result = test_cases[metric_name][1]
            expected = test_cases[metric_name][2]

            # Post build 1 results
            self.receive_test_run(self.project, self.build_a.version, self.environment_a.slug, {
                metric_name: build_a_result,
            })

            # Post build 2 results
            self.receive_test_run(self.project, self.build_b.version, self.environment_a.slug, {
                metric_name: build_b_result,
            })

            comparison = MetricComparison(self.build_a, self.build_b, regressions_and_fixes_only=True)
            if expected is True:
                self.assertIn(metric_name, comparison.fixes[self.environment_a.slug])
            elif expected is False:
                self.assertIn(metric_name, comparison.regressions[self.environment_a.slug])
            else:
                self.assertNotIn(metric_name, comparison.regressions[self.environment_a.slug])
                self.assertNotIn(metric_name, comparison.fixes[self.environment_a.slug])

    def different_environments(self):
        metric_name = 'suite_a/different-env-metric'
        build_a_result = 1
        build_b_result = 2

        # Post build 1 results
        self.receive_test_run(self.project, self.build_a.version, self.environment_a.slug, {
            metric_name: build_a_result,
        })

        # Post build 2 results
        self.receive_test_run(self.project, self.build_b.version, self.environment_b.slug, {
            metric_name: build_b_result,
        })

        comparison = MetricComparison(self.build_a, self.build_b, regressions_and_fixes_only=True)
        self.assertEqual(0, len(comparison.regressions))
        self.assertEqual(0, len(comparison.fixes))

    def different_suites(self):
        metric_name = 'different-suite-metric'
        build_a_result = 1
        build_b_result = 2

        # Post build 1 results
        self.receive_test_run(self.project, self.build_a.version, self.environment_a.slug, {
            'suite_a/' + metric_name: build_a_result,
        })

        # Post build 2 results
        self.receive_test_run(self.project, self.build_b.version, self.environment_a.slug, {
            'suite_b/' + metric_name: build_b_result,
        })

        comparison = MetricComparison(self.build_a, self.build_b, regressions_and_fixes_only=True)
        self.assertEqual(0, len(comparison.regressions))
        self.assertEqual(0, len(comparison.fixes))
