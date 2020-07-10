from django.test import TestCase
from squad.core.models import Group, TestRun, Attachment


class TestAttachment(TestCase):
    def test_basics(self):
        group = Group.objects.create(slug="mygroup")
        project = group.projects.create(slug="myproject")
        build = project.builds.create(version="1")
        env = project.environments.create(slug="myenv")
        test_run = TestRun.objects.create(build=build, environment=env)

        attachment = Attachment(
            test_run=test_run, data="abc".encode("utf-8"), length=3, filename="foo.txt"
        )
        attachment.save()

        fromdb = Attachment.objects.get(pk=attachment.pk)
        self.assertEqual(b"abc", bytes(fromdb.data))
