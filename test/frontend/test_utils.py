from django.test import TestCase

from squad.core.models import Group, Project
from squad.frontend.utils import file_type, alphanum_sort


class FileTypeTest(TestCase):

    def test_text(self):
        self.assertEqual('text', file_type('foo.txt'))

    def test_code(self):
        self.assertEqual('code', file_type('foo.py'))
        self.assertEqual('code', file_type('foo.sh'))

    def test_image(self):
        self.assertEqual('image', file_type('foo.png'))
        self.assertEqual('image', file_type('foo.jpg'))


class AlphaNumSortTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.p1 = self.group.projects.create(slug='project1', name='project-v1.1')
        self.p2 = self.group.projects.create(slug='project2', name='project-v1.10')
        self.p3 = self.group.projects.create(slug='project3', name='project-v1.2')

    def test_asc_sort(self):
        projects = Project.objects.all()
        projects_sorted = alphanum_sort(projects, 'name', reverse=False)
        # v1.1 -> v1.2 -> v1.10
        self.assertEqual([self.p1, self.p3, self.p2], projects_sorted)

    def test_desc_sort(self):
        projects = Project.objects.all()
        projects_sorted = alphanum_sort(projects, 'name')
        # v1.10 -> v1.2 -> v1.1
        self.assertEqual([self.p2, self.p3, self.p1], projects_sorted)
