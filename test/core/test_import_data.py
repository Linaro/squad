import os


from django.test import TestCase

from squad.core.models import Build, Group, TestRun, Metric, Test
from squad.core.management.commands.import_data import Command


class ImportTest(TestCase):

    def setUp(self):
        self.importer = Command()
        self.importer.silent = True

        d = os.path.join(os.path.dirname(__file__), 'test_import_data_input')
        self.importer.handle(PROJECT='foo/bar', DIRECTORY=d)

    def test_import_basics(self):
        group = Group.objects.get(slug='foo')
        project = group.projects.get(slug='bar')

        self.assertEqual(2, project.builds.count())
        builds = [row['version'] for row in project.builds.values('version')]
        self.assertEqual(['1', '2'], sorted(builds))

        self.assertEqual(1, project.builds.all()[0].test_runs.count())
        self.assertEqual(1, project.builds.all()[1].test_runs.count())

    def test_import_dates(self):
        dates = [t.datetime for t in TestRun.objects.all()]
        self.assertIsNotNone(dates[0])
        self.assertEqual(dates[0], dates[1])

    def test_import_metrics(self):
        self.assertEqual(2, Metric.objects.count())

    def test_import_tests(self):
        self.assertEqual(1, Test.objects.count())

    def test_import_attachments(self):
        t = Build.objects.get(version='2').test_runs.last()
        self.assertIsNotNone(t.attachments.get(filename='screenshot.png'))
