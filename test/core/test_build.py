from django.test import TestCase


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
        newer = Build.objects.create(project=self.project, version='1.1')
        Build.objects.create(project=self.project, version='1.0')

        self.assertEqual(newer, Build.objects.last())
