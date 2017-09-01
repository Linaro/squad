from django.test import TestCase
from squad.core.models import Group, TestRun


class TestRunTest(TestCase):

    def test_metadata(self):
        t = TestRun(metadata_file='{"1": 2}')
        self.assertEqual({"1": 2}, t.metadata)

    def test_no_metadata(self):
        self.assertEqual({}, TestRun().metadata)

    def test_manipulate_metadata(self):
        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
        build = project.builds.create(version='1')
        env = project.environments.create(slug='myenv')
        t = TestRun(build=build, environment=env)
        t.metadata["foo"] = "bar"
        t.metadata["baz"] = "qux"
        t.save()
        t.refresh_from_db()

        self.assertEqual({"foo": "bar", "baz": "qux"}, t.metadata)
