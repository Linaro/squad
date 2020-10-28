from io import StringIO
from django.core.files import File
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
        testrun = TestRun.objects.create(build=self.build, environment=self.env)

        self.assertFalse(testrun.tests_file_storage)
        tests_file_contents = StringIO('tests file content')
        tests_file = File(tests_file_contents)
        storage_filename = "testrun/%s/tests_file" % (testrun.id)
        testrun.tests_file_storage.save(storage_filename, tests_file)

        self.assertFalse(testrun.metrics_file_storage)
        metrics_file_contents = StringIO('metrics file content')
        metrics_file = File(metrics_file_contents)
        storage_filename = "testrun/%s/metrics_file" % (testrun.id)
        testrun.metrics_file_storage.save(storage_filename, metrics_file)

        self.assertFalse(testrun.log_file_storage)
        log_file_contents = StringIO('log file content')
        log_file = File(log_file_contents)
        storage_filename = "testrun/%s/log_file" % (testrun.id)
        testrun.log_file_storage.save(storage_filename, log_file)
