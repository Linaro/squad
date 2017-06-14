from django.utils import timezone
from django.test import TestCase
from dateutil.relativedelta import relativedelta

from squad.core.models import Group, ProjectStatus


def h(n):
    """
    h(n) = n hours ago
    """
    return timezone.now() - relativedelta(hours=n)


class ProjectStatusTest(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        self.project = group.projects.create(slug='myproject')
        self.environment = self.project.environments.create(slug='theenvironment')

    def create_build(self, v, datetime=None, create_test_run=True):
        build = self.project.builds.create(version=v, datetime=datetime)
        if create_test_run:
            build.test_runs.create(environment=self.environment)
        return build

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
        self.create_build('1', datetime=h(1), create_test_run=False)
        status = ProjectStatus.create(self.project)
        self.assertIsNone(status)

    def test_first_build(self):
        build = self.create_build('1')
        status = ProjectStatus.create(self.project)
        self.assertEqual(build, status.build)

    def test_last_build_not_finished(self):
        self.create_build('0', datetime=h(10))
        ProjectStatus.create(self.project)
        b1 = self.create_build('1', datetime=h(5))
        self.create_build('2', datetime=h(4), create_test_run=False)
        status = ProjectStatus.create(self.project)
        self.assertEqual(b1, status.build)

    def test_status_with_multiple_builds(self):
        self.create_build('1', datetime=h(10))
        ProjectStatus.create(self.project)

        b1 = self.create_build('2', datetime=h(5))
        b2 = self.create_build('3', datetime=h(4))

        status = ProjectStatus.create(self.project)
        self.assertEqual([b1, b2], list(status.builds))
