from django.test import TestCase
from mock import patch
import yaml


from squad.ci.models import Backend, TestJob
from squad.ci.backend.lava import Backend as LAVABackend


TEST_RESULTS = [
]


TEST_RESULTS_YAML = yaml.dump(TEST_RESULTS)


class LavaTest(TestCase):

    def setUp(self):
        self.backend = Backend.objects.create(
            url='http://example.com/',
            username='myuser',
            token='mypassword',
            implementation_type='lava',
        )

    def test_detect(self):
        impl = self.backend.get_implementation()
        self.assertIsInstance(impl, LAVABackend)

    @patch("squad.ci.backend.lava.Backend.__submit__", return_value='1234')
    def test_submit(self, __submit__):
        testjob = TestJob(definition="foo: 1\n")
        lava = LAVABackend(None)
        self.assertEqual('1234', lava.submit(testjob))
        __submit__.assert_called_with("foo: 1\n")

    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value={"status": "Complete"})
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_YAML)
    def test_fetch_basics(self, get_results, get_details):
        testjob = TestJob(job_id='9999')
        lava = LAVABackend(None)
        results = lava.fetch(testjob)

        get_details.assert_called_with('9999')
        get_results.assert_called_with('9999')
        self.assertEqual('Complete', results[0])

    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value={"status": "Running"})
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__")
    def test_fetch_not_finished(self, get_results, get_details):
        testjob = TestJob(job_id='9999')
        lava = LAVABackend(None)
        lava.fetch(testjob)

        get_results.assert_not_called()

    def test_parse_results_metadata(self):
        pass  # TODO

    def test_parse_results_tests(self):
        pass  # TODO

    def test_parse_results_metrics(self):
        pass  # TODO
