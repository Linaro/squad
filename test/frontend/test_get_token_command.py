from django.test import TestCase
from test.mock import patch

from squad.core.models import Project
from squad.frontend.management.commands.get_token import Command


class TestCommand(TestCase):

    @patch('squad.frontend.management.commands.get_token.Command.output')
    def test_basics(self, output):
        command = Command()
        command.handle(PROJECT='foo/bar')
        project = Project.objects.get(group__slug='foo', slug='bar')
        self.assertEqual(project.group.members.count(), 1)

    @patch('squad.frontend.management.commands.get_token.Command.output')
    def test_is_idempotent(self, output):
        command = Command()
        command.handle(PROJECT='foo/bar')
        command.handle(PROJECT='foo/bar')
        project = Project.objects.get(group__slug='foo', slug='bar')
        self.assertEqual(project.group.members.count(), 1)
