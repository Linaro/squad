from django.test import TestCase


from squad.core.models import Group, TestRun
from squad.core.tasks import ParseTestRunData


class ParseTestRunDataTest(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='mygroup')
        build = project.builds.create(version='1.0.0')
        env = project.environments.create(slug='myenv')
        self.testrun = TestRun.objects.create(
            build=build,
            environment=env,
            tests_file='{"foobar/test1": "pass"}',
            metrics_file='{"foobar/metric1": 10}',
        )

    def test_basics(self):
        ParseTestRunData()(self.testrun)

        self.assertEqual(1, self.testrun.tests.count())
        self.assertEqual(1, self.testrun.metrics.count())

    def test_does_not_process_twice(self):
        ParseTestRunData()(self.testrun)
        ParseTestRunData()(self.testrun)

        self.assertEqual(1, self.testrun.tests.count())
        self.assertEqual(1, self.testrun.metrics.count())
