from django.core.management import call_command
from django.test import TestCase

from squad.core.models import Group, Test


class ImportTest(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(slug='foo')
        project, _ = group.projects.get_or_create(slug='bar')
        env, _ = project.environments.get_or_create(slug='env')
        build, _ = project.builds.get_or_create(version='build')
        self.testrun, _ = build.test_runs.get_or_create(environment=env)
        self.suite, _ = project.suites.get_or_create(slug='suite')

    def test_basics(self):
        test, _ = self.testrun.tests.get_or_create(name='test_name', suite=self.suite)

        self.assertIsNone(test.metadata)

        call_command('fill_test_metadata')

        test.refresh_from_db()
        self.assertIsNotNone(test.metadata)

    def test_batch(self):
        test1, _ = self.testrun.tests.get_or_create(name='test_name1', suite=self.suite)
        test2, _ = self.testrun.tests.get_or_create(name='test_name2', suite=self.suite)

        self.assertIsNone(test1.metadata)
        self.assertIsNone(test2.metadata)

        call_command('fill_test_metadata', '--batch-size', '1')

        tests = Test.objects.filter(metadata__isnull=True)
        self.assertEqual(1, tests.count())
