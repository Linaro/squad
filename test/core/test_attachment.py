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

        data = 'abc'.encode('utf-8')
        filename = 'foo.txt'
        attachment = Attachment(
            test_run=self.test_run, length=3, filename=filename
        )
        attachment.save()
        attachment.save_file(filename, data)

        fromdb = Attachment.objects.get(pk=attachment.pk)
        self.assertEqual(b"abc", fromdb.data)

    def test_storage_fields(self):
        filename = 'foo.txt'
        contents = b'attachment file content'
        attachment = Attachment.objects.create(test_run=self.test_run, filename=filename, length=len(contents))

        self.assertFalse(attachment.storage)

        attachment.save_file(filename, contents)

        attachment.refresh_from_db()

        self.assertEqual(contents, attachment.storage.read())
