from django.test import TestCase


from squad.core.models import User, Group, UserNamespace


class UserNamespaceTest(TestCase):

    def test_slug_basic(self):
        userns = UserNamespace.objects.create(slug='~foo')
        self.assertIsInstance(userns, Group)

    def test_create_for(self):
        user = User.objects.create(username='foo')
        userns = UserNamespace.objects.create_for(user)
        self.assertEqual('~foo', userns.slug)
        self.assertTrue(userns.writable_by(user))

    def test_get_or_create_for(self):
        user = User.objects.create(username='foo')
        userns1 = UserNamespace.objects.get_or_create_for(user)
        userns2 = UserNamespace.objects.get_or_create_for(user)
        self.assertEqual(userns1, userns2)

    def test_get_only_user_namespaces(self):
        Group.objects.create(slug='thegroup')
        userns = UserNamespace.objects.create(slug='~foo')
        self.assertEqual([userns], list(UserNamespace.objects.all()))
