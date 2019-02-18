from django.test import TestCase
from django.contrib.auth.models import AnonymousUser


from django.contrib.auth.models import Group as UserGroup, User
from squad.core.models import Group


class GroupTest(TestCase):
    def setUp(self):
        self.user_group = UserGroup.objects.create(name='mygroup')
        self.user1 = User.objects.create(username='u1')
        self.user1.groups.add(self.user_group)

        self.user2 = User.objects.create(username='u2')

        self.admin = User.objects.create(username='admin', is_superuser=True)

        self.group = Group.objects.create(slug='mygroup')
        self.group.user_groups.add(self.user_group)

    def test_accessible_manager_non_member(self):
        self.assertEqual(
            [],
            list(Group.objects.accessible_to(self.user2))
        )

    def test_accessible_manager_member(self):
        self.assertEqual(
            [self.group],
            list(Group.objects.accessible_to(self.user1))
        )

    def test_accessible_manager_anonymous_user(self):
        self.assertEqual(
            [],
            list(Group.objects.accessible_to(AnonymousUser()))
        )

    def test_accessible_manager_admin(self):
        self.assertEqual(
            [self.group],
            list(Group.objects.accessible_to(self.admin))
        )

    def test_count_accessible_projects(self):
        self.group.projects.create(slug='foo')
        self.group.projects.create(slug='bar', is_public=False)

        admin_groups = list(Group.objects.accessible_to(self.admin))
        self.assertEqual(admin_groups[0].project_count, 2)

        member_groups = list(Group.objects.accessible_to(self.user1))
        self.assertEqual(member_groups[0].project_count, 2)

        anonymous_user_groups = list(Group.objects.accessible_to(AnonymousUser()))
        self.assertEqual(anonymous_user_groups[0].project_count, 1)
