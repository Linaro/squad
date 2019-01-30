from datetime import datetime

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from squad.core.models import Group, ProjectStatus


class UpdateStatusesTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.environment = self.project.environments.create(slug='theenvironment')
        self.suite = self.project.suites.create(slug='/')

    def create_build(self, v, datetime=None, create_test_run=True):
        build = self.project.builds.create(version=v, datetime=datetime)
        if create_test_run:
            build.test_runs.create(environment=self.environment)
        return build

    def test_update_status(self):
        build1 = self.create_build('1')
        build1.datetime = timezone.make_aware(datetime(2018, 6, 1))
        build1.save()

        status1 = ProjectStatus.objects.first()
        status1.fixes = "fixes1"
        status1.finished = True
        status1.save()

        self.create_build('2')
        status2 = ProjectStatus.objects.last()
        status2.fixes = "fixes2"
        status2.finished = True
        status2.save()

        call_command('update_project_statuses', "--date-start", "2018-07-01")

        status1.refresh_from_db()
        status2.refresh_from_db()

        self.assertEqual(status1.fixes, "fixes1")
        self.assertNotEqual(status2.fixes, "fixes2")
