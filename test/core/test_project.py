from django.test import TestCase
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError


from django.contrib.auth.models import Group as UserGroup, User
from squad.core.models import Group, Project, Token


class ProjectTest(TestCase):

    def setUp(self):
        self.user_group = UserGroup.objects.create(name='mygroup')
        self.user1 = User.objects.create(username='u1')
        self.user1.groups.add(self.user_group)

        self.user2 = User.objects.create(username='u2')

        self.admin = User.objects.create(username='admin', is_superuser=True)

        self.group = Group.objects.create(slug='mygroup')
        self.group.user_groups.add(self.user_group)

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
