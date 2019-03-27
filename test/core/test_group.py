from django.core.exceptions import ValidationError
from django.test import TestCase
from django.contrib.auth.models import AnonymousUser


from django.contrib.auth.models import User
from squad.core.models import Group


class GroupTest(TestCase):
    def setUp(self):
        self.member = User.objects.create(username='u1')

        self.non_member = User.objects.create(username='u2')

        self.admin = User.objects.create(username='admin', is_superuser=True)

        self.group = Group.objects.create(slug='mygroup')
        self.group.add_admin(self.member)

    def test_accessible_manager_non_member(self):
        self.assertEqual(
            [],
            list(Group.objects.accessible_to(self.non_member))
        )

    def test_accessible_manager_member(self):
        self.assertEqual(
            [self.group],
            list(Group.objects.accessible_to(self.member))
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

        member_groups = list(Group.objects.accessible_to(self.member))
        self.assertEqual(member_groups[0].project_count, 2)

        anonymous_user_groups = list(Group.objects.accessible_to(AnonymousUser()))
        self.assertEqual(anonymous_user_groups[0].project_count, 1)

    def test_writable_by(self):
        self.assertTrue(self.group.writable_by(self.member))
        self.assertFalse(self.group.writable_by(self.non_member))


class TestGroupSlug(TestCase):

    def test_does_not_accept_user_namespace_slug(self):
        with self.assertRaises(ValidationError):
            Group(slug='~foo').full_clean()

    def test_invalid_slug(self):
        group = Group(slug='foo/bar')
        with self.assertRaises(ValidationError):
            group.full_clean()
        group.slug = 'foo-bar'
        group.full_clean()  # if this raises no exception, we are fine
