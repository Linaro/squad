from django.core.exceptions import ValidationError
from django.test import TestCase
from django.contrib.auth.models import AnonymousUser


from django.contrib.auth.models import User
from squad.core.models import Group, Project


class ProjectTest(TestCase):

    def setUp(self):
        self.user1 = User.objects.create(username='u1')

        self.user2 = User.objects.create(username='u2')

        self.admin = User.objects.create(username='admin', is_superuser=True)

        self.group = Group.objects.create(slug='mygroup')
        self.group.add_admin(self.user1)

        self.public_project = self.group.projects.create(slug='public')
        self.private_project = self.group.projects.create(slug='private', is_public=False)

    def test_accessible_manager_non_member(self):
        self.assertEqual(
            [self.public_project],
            list(Project.objects.accessible_to(self.user2))
        )

    def test_accessible_manager_member(self):
        self.assertEqual(
            [self.public_project, self.private_project],
            list(Project.objects.accessible_to(self.user1).order_by('id'))
        )

    def test_accessible_manager_anonymous_user(self):
        self.assertEqual(
            [self.public_project],
            list(Project.objects.accessible_to(AnonymousUser()))
        )

    def test_accessible_manager_admin(self):
        self.assertEqual(
            [self.public_project.id, self.private_project.id],
            sorted([p.id for p in Project.objects.accessible_to(self.admin)])
        )

    def test_accessible_instance_non_member(self):
        self.assertFalse(self.private_project.accessible_to(self.user2))

    def test_accessible_instance_member(self):
        self.assertTrue(self.private_project.accessible_to(self.user1))

    def test_accessible_instance_public_project_non_member(self):
        self.assertTrue(self.public_project.accessible_to(self.user2))

    def test_accessible_instance_public_project_anonymous_user(self):
        self.assertTrue(self.public_project.accessible_to(AnonymousUser()))

    def test_accessible_instance_admin(self):
        self.assertTrue(self.private_project.accessible_to(self.admin))

    def test_enabled_plugins_empty(self):
        self.assertIsNone(Project().enabled_plugins)
        self.assertEqual([], Project(enabled_plugins_list=[]).enabled_plugins)

    def test_enabled_plugins(self):
        p = Project(enabled_plugins_list=['aaa', 'bbb'])
        self.assertEqual(['aaa', 'bbb'], p.enabled_plugins)

    def test_invalid_slug(self):
        p = Project(group=self.group, slug='foo/bar')
        with self.assertRaises(ValidationError):
            p.full_clean()
        p.slug = 'foo-bar'
        p.full_clean()  # it this raises no exception, then we are fine

    def test_validate_project_settings(self):
        p = Project(group=self.group, slug='foobar', project_settings='1')
        with self.assertRaises(ValidationError):
            p.full_clean()
        p.project_settings = 'foo: bar\n'
        p.full_clean()

    def test_get_project_settings(self):
        p = Project.objects.create(group=self.group, slug='foobar', project_settings='{"setting1": "value"}')
        self.assertEqual("value", p.get_setting("setting1"))
        self.assertEqual(None, p.get_setting("unkown_setting"))
        self.assertEqual("default", p.get_setting("unkown_setting", "default"))
