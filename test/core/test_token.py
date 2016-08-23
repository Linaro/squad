from django.test import TestCase

from squad.core.models import Group, Project, Token


class TokenTest(TestCase):

    def new_token(self):
        group, _ = Group.objects.get_or_create(name='My group')
        project, _ = group.projects.get_or_create(name='My project')
        return Token.objects.create(description='my token', project=project)

    def test_random_token(self):
        token = self.new_token()
        self.assertTrue(len(token.key) > 0)
