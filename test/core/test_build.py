from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.utils import timezone


from squad.core.models import Group, Build


class BuildTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')

    def test_version_from_name(self):
        b = Build.objects.create(project=self.project, name='1.0-rc1')
        self.assertEqual('1.0~rc1', b.version)

    def test_name_from_version(self):
        b = Build.objects.create(project=self.project, version='1.0-rc1')
        self.assertEqual('1.0-rc1', b.name)
        self.assertEqual('1.0~rc1', b.version)

    def test_default_ordering(self):
        now = timezone.now()
        before = now - relativedelta(hours=1)
        newer = Build.objects.create(project=self.project, version='1.1', datetime=now)
        Build.objects.create(project=self.project, version='1.0', datetime=before)

        self.assertEqual(newer, Build.objects.last())

    def test_test_summary(self):
        build = Build.objects.create(project=self.project, version='1.1')
        env = self.project.environments.create(slug='env')
        suite = self.project.suites.create(slug='tests')
        test_run = build.test_runs.create(environment=env)
        test_run.tests.create(name='foo', suite=suite, result=True)
        test_run.tests.create(name='bar', suite=suite, result=False)

        self.assertEqual({'total': 2, 'pass': 1, 'fail': 1}, build.test_summary)
