import os
from django.test import TestCase
from squad.core.models import Group, TestRun


class TestRunTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.build = self.project.builds.create(version='1')
        self.env = self.project.environments.create(slug='myenv')

    def test_metadata(self):
        t = TestRun(metadata_file='{"1": 2}')
        self.assertEqual({"1": 2}, t.metadata)

    def test_no_metadata(self):
        self.assertEqual({}, TestRun().metadata)

    def test_manipulate_metadata(self):
        t = TestRun(build=self.build, environment=self.env)
        t.metadata["foo"] = "bar"
        t.metadata["baz"] = "qux"
        t.save()
        t.refresh_from_db()

        self.assertEqual({"foo": "bar", "baz": "qux"}, t.metadata)

    def test_storage_fields(self):
        tests_file_content = 'tests file content'
        metrics_file_content = 'metrics file content'
        log_file_content = 'log file content'

        testrun = TestRun.objects.create(
            build=self.build,
            environment=self.env)

        self.assertFalse(testrun.tests_file_storage)
        self.assertFalse(testrun.metrics_file_storage)
        self.assertFalse(testrun.log_file_storage)

        testrun.save_tests_file(tests_file_content)
        testrun.save_metrics_file(metrics_file_content)
        testrun.save_log_file(log_file_content)

        self.assertEqual(tests_file_content, testrun.tests_file_storage.read().decode())
        self.assertEqual(metrics_file_content, testrun.metrics_file_storage.read().decode())
        self.assertEqual(log_file_content, testrun.log_file_storage.read().decode())

    def test_delete_storage_fields_on_model_deletion(self):
        tests_file_content = 'tests file content'
        metrics_file_content = 'metrics file content'
        log_file_content = 'log file content'
        attachment_content = b'attachment content'
        attachment_filename = 'foo.txt'

        testrun = TestRun.objects.create(
            build=self.build,
            environment=self.env)

        attachment = testrun.attachments.create(filename=attachment_filename, length=len(attachment_content))

        self.assertFalse(testrun.tests_file_storage)
        self.assertFalse(testrun.metrics_file_storage)
        self.assertFalse(testrun.log_file_storage)
        self.assertFalse(attachment.storage)

        testrun.refresh_from_db()
        testrun.save_tests_file(tests_file_content)
        testrun.save_metrics_file(metrics_file_content)
        testrun.save_log_file(log_file_content)
        attachment.save_file(attachment_filename, attachment_content)
        attachment.refresh_from_db()

        self.assertEqual(tests_file_content, testrun.tests_file_storage.read().decode())
        self.assertEqual(metrics_file_content, testrun.metrics_file_storage.read().decode())
        self.assertEqual(log_file_content, testrun.log_file_storage.read().decode())
        self.assertEqual(attachment_content, attachment.storage.read())

        tests_file_storage_path = testrun.tests_file_storage.path
        metrics_file_storage_path = testrun.metrics_file_storage.path
        log_file_storage_path = testrun.log_file_storage.path
        attachment_storage_path = attachment.storage.path

        testrun.delete()

        self.assertFalse(os.path.isfile(tests_file_storage_path))
        self.assertFalse(os.path.isfile(metrics_file_storage_path))
        self.assertFalse(os.path.isfile(log_file_storage_path))
        self.assertFalse(os.path.isfile(attachment_storage_path))
