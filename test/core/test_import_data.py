import os


from django.test import TestCase

from squad.core.models import Group, TestRun, Metric
from squad.core.management.commands.import_data import Command


class ImportTest(TestCase):

    def setUp(self):
        self.importer = Command()
        self.importer.silent = True

    def test_import_basics(self):
        d = os.path.join(os.path.dirname(__file__), 'test_import_data_input')
        self.importer.handle(PROJECT='foo/bar', DIRECTORY=d)

        group = Group.objects.get(slug='foo')
        project = group.projects.get(slug='bar')

        self.assertEqual(2, project.builds.count())
        builds = [row['version'] for row in project.builds.values('version')]
        self.assertEqual(['1', '2'], sorted(builds))

        self.assertEqual(1, project.builds.all()[0].test_runs.count())
        self.assertEqual(1, project.builds.all()[1].test_runs.count())

        dates = [t.datetime for t in TestRun.objects.all()]
        self.assertIsNotNone(dates[0])
        self.assertEqual(dates[0], dates[1])

        self.assertEqual(2, Metric.objects.count())
