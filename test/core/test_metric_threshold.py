from django.core.exceptions import ValidationError
from django.test import TestCase


from squad.core.models import Group


class MetricThresholdTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.environment = self.project.environments.create(slug='myenv')

    def test_basic(self):
        threshold_name = 'sample-threshold'
        self.project.thresholds.create(name=threshold_name)
        m = self.project.thresholds.filter(name=threshold_name)
        self.assertEqual(1, m.count())

    def test_all_attributes(self):
        threshold_name = 'sample-threshold'
        value = 1
        is_higher_better = True
        env = self.environment

        self.project.thresholds.create(name=threshold_name, value=value, is_higher_better=is_higher_better, environment=env)
        m = self.project.thresholds.filter(name=threshold_name, value=value, is_higher_better=is_higher_better, environment=env)
        self.assertEqual(1, m.count())

    def test_fail_to_duplicate(self):
        # There are 2 types of duplicates:
        # 1. When there's a threshold for all envs, and a new one for a specific env is added
        threshold_name = 'all-envs-threshold'
        self.project.thresholds.create(name=threshold_name)
        with self.assertRaises(ValidationError):
            self.project.thresholds.create(name=threshold_name, environment=self.environment)

        # 2. When there's a threshold for a specific env, and a new one for all envs is added
        threshold_name = 'specific-env-threshold'
        self.project.thresholds.create(name=threshold_name, environment=self.environment)
        with self.assertRaises(ValidationError):
            self.project.thresholds.create(name=threshold_name)

    def test_matches_correct_metrics(self):
        # A threshold name is used as a regex to match metrics' names
        # therefore it should not match metrics it is not supposed to
        threshold_name = 'should-not-match-beyong-here'
        threshold = self.project.thresholds.create(name=threshold_name)
        self.assertFalse(threshold.match(threshold_name + '-very-similar-metric-name'))

        # It should, though, match the correct things
        threshold_name = 'should-match-*-of-these'
        threshold = self.project.thresholds.create(name=threshold_name)
        self.assertTrue(threshold.match('should-match-any-of-these'))
        self.assertTrue(threshold.match('should-match-all-of-these'))

        # It should NOT parse any other regex special character
        threshold_name = 'should-not-match-that-[0-9]'
        threshold = self.project.thresholds.create(name=threshold_name)
        self.assertFalse(threshold.match('should-not-match-that-0'))
