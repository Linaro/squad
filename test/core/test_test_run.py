from django.test import TestCase
from squad.core.models import TestRun


class TestRunTest(TestCase):

    def test_metadata(self):
        t = TestRun(metadata_file='{"1": 2}')
        self.assertEqual({"1": 2}, t.metadata)

    def test_no_metadata(self):
        self.assertEqual({}, TestRun().metadata)
