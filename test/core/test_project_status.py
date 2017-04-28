from django.utils import timezone
from django.test import TestCase
from dateutil.relativedelta import relativedelta

from squad.core.models import Group, ProjectStatus


class ProjectStatusTest(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        self.project = group.projects.create(slug='myproject', build_completion_threshold=120)

    def create_build(self, v, **kwargs):
        two_hours_ago = timezone.now() - relativedelta(hours=2)
        args = {'datetime': two_hours_ago}
        args.update(kwargs)
        return self.project.builds.create(version=v, **args)

    def test_status_without_builds(self):
        status = ProjectStatus.create(self.project)
        self.assertIsNone(status)
        self.assertEqual(0, ProjectStatus.objects.count())

    def test_status_of_first_build(self):
        build = self.create_build('1')
        status = ProjectStatus.create(self.project)

        self.assertEqual(build, status.build)
        self.assertIsNone(status.previous)

    def test_status_of_second_build(self):
        self.create_build('1')
        status1 = ProjectStatus.create(self.project)

        build2 = self.create_build('2')
        status2 = ProjectStatus.create(self.project)
        self.assertEqual(status1, status2.previous)
        self.assertEqual(build2, status2.build)

    def test_dont_record_the_same_status_twice(self):
        self.create_build('1')
        ProjectStatus.create(self.project)
        self.assertIsNone(ProjectStatus.create(self.project))
        self.assertEqual(1, ProjectStatus.objects.count())

    def test_wait_for_build_completion(self):
        self.create_build('1', datetime=timezone.now() - relativedelta(hours=1))
        status = ProjectStatus.create(self.project)
        self.assertIsNone(status)
