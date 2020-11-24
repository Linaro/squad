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
            environment=self.env,
            old_tests_file=tests_file_content,
            old_metrics_file=metrics_file_content,
            old_log_file=log_file_content)

        self.assertFalse(testrun.tests_file_storage)
        self.assertFalse(testrun.metrics_file_storage)
        self.assertFalse(testrun.log_file_storage)

        testrun.save_files()

        self.assertEqual(tests_file_content, testrun.tests_file_storage.read().decode())
        self.assertEqual(metrics_file_content, testrun.metrics_file_storage.read().decode())
        self.assertEqual(log_file_content, testrun.log_file_storage.read().decode())
