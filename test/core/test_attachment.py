from django.test import TestCase
from squad.core.models import Group, TestRun, Attachment


class TestAttachment(TestCase):
    def setUp(self):
        self.group = Group.objects.create(slug="mygroup")
        self.project = self.group.projects.create(slug="myproject")
        self.build = self.project.builds.create(version="1")
        self.env = self.project.environments.create(slug="myenv")
        self.test_run = TestRun.objects.create(build=self.build, environment=self.env)

    def test_basics(self):

        attachment = Attachment(
            test_run=self.test_run, old_data="abc".encode("utf-8"), length=3, filename="foo.txt"
        )
        attachment.save()

        self.test_run.save_files()

        fromdb = Attachment.objects.get(pk=attachment.pk)
        self.assertEqual(b"abc", fromdb.data)

    def test_storage_fields(self):
        contents = b'attachment file content'
        attachment = Attachment.objects.create(test_run=self.test_run, filename="foo.txt", length=len(contents), old_data=contents)

        self.assertFalse(attachment.storage)

        self.test_run.save_files()

        attachment.refresh_from_db()

        self.assertEqual(contents, attachment.storage.read())
