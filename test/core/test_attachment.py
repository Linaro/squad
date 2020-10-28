from io import BytesIO
from django.core.files import File
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
            test_run=self.test_run, data="abc".encode("utf-8"), length=3, filename="foo.txt"
        )
        attachment.save()

        fromdb = Attachment.objects.get(pk=attachment.pk)
        self.assertEqual(b"abc", bytes(fromdb.data))

    def test_storage_fields(self):
        contents = 'attachment file content'
        attachment = Attachment.objects.create(test_run=self.test_run, filename="foo.txt", length=len(contents))

        self.assertFalse(attachment.storage)
        contents = BytesIO(contents.encode())
        contents_file = File(contents)
        storage_filename = "attachment/%s/%s" % (attachment.id, attachment.filename)
        attachment.storage.save(storage_filename, contents_file)
