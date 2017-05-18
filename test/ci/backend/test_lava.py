from django.test import TestCase
from mock import patch, MagicMock
import yaml
import xmlrpc


from squad.ci.models import Backend, TestJob
from squad.ci.backend.lava import Backend as LAVABackend
from squad.ci.exceptions import SubmissionIssue, TemporarySubmissionIssue


TEST_RESULTS = [
    {'duration': '',
     'job': '1234',
     'level': 'None',
     'logged': '2017-02-15 11:31:21.973616+00:00',
     'measurement': '10',
     'metadata': {'case': 'case_foo',
                  'definition': '1_DefinitionFoo',
                  'measurement': '10',
                  'result': 'pass',
                  'units': 'bottles'},
     'name': 'case_foo',
     'result': 'pass',
     'suite': '1_DefinitionFoo',
     'timeout': '',
     'unit': 'bottles',
     'url': '/results/1234/1_DefinitionFoo/case_foo'},
    {'duration': '',
     'job': '1234',
     'level': 'None',
     'logged': '2017-02-15 11:31:21.973616+00:00',
     'measurement': 'None',
     'metadata': {'case': 'case_bar',
                  'definition': '1_DefinitionFoo',
                  'measurement': 'None',
                  'result': 'pass'},
     'name': 'case_bar',
     'result': 'pass',
     'suite': '1_DefinitionFoo',
     'timeout': '',
     'unit': '',
     'url': '/results/1234/1_DefinitionFoo/case_bar'},
]

JOB_METADATA = {
    'key_foo': 'value_foo',
    'key_bar': 'value_bar'
}


JOB_DEFINITION = {
    'job_name': 'job_foo',
    'metadata': JOB_METADATA
}

JOB_DETAILS = {
    'is_pipeline': True,
    'status': 'Complete',
    'id': 1234,
    'definition': yaml.dump(JOB_DEFINITION),
    'multinode_definition': ''
}

JOB_DETAILS_RUNNING = {
    'is_pipeline': True,
    'status': 'Running',
    'id': 1234,
    'definition': yaml.dump(JOB_DEFINITION),
    'multinode_definition': ''
}


TEST_RESULTS_YAML = yaml.dump(TEST_RESULTS)


HTTP_400 = xmlrpc.client.Fault(400, 'Problem with submitted job data')
HTTP_503 = xmlrpc.client.Fault(503, 'Service Unavailable')
HTTP_401 = xmlrpc.client.ProtocolError('http://example.com', 401, 'Unauthorized', {})


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
        lava = LAVABackend(None)
        testjob = TestJob(
            definition="foo: 1\n",
            backend=self.backend)
        self.assertEqual('1234', lava.submit(testjob))
        __submit__.assert_called_with("foo: 1\n")

    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_YAML)
    def test_fetch_basics(self, get_results, get_details):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='9999',
            backend=self.backend)
        results = lava.fetch(testjob)

        get_details.assert_called_with('9999')
        get_results.assert_called_with('9999')
        self.assertEqual('Complete', results[0])

    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS_RUNNING)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__")
    def test_fetch_not_finished(self, get_results, get_details):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='9999',
            backend=self.backend)
        lava.fetch(testjob)

        get_results.assert_not_called()

    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_YAML)
    def test_parse_results_metadata(self, get_results, get_details):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        status, metadata, results, metrics = lava.fetch(testjob)

        self.assertEqual(JOB_METADATA, metadata)

    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_YAML)
    def test_parse_results(self, get_results, get_details):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        status, metadata, results, metrics = lava.fetch(testjob)

        self.assertEqual(len(results), 1)
        self.assertEqual(len(metrics), 1)

    @patch('squad.ci.backend.lava.Backend.__submit__', side_effect=HTTP_400)
    def test_submit_400(self, __submit__):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        with self.assertRaises(SubmissionIssue):
            lava.submit(testjob)

    @patch('squad.ci.backend.lava.Backend.__submit__', side_effect=HTTP_503)
    def test_submit_503(self, __submit__):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        with self.assertRaises(TemporarySubmissionIssue):
            lava.submit(testjob)

    @patch('squad.ci.backend.lava.Backend.__submit__', side_effect=HTTP_401)
    def test_submit_unauthorized(self, __submit__):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        with self.assertRaises(TemporarySubmissionIssue):
            lava.submit(testjob)

    def test_get_listen_url(self):
        backend = MagicMock()
        backend.url = 'https://foo.tld/RPC2'
        lava = LAVABackend(backend)

        lava.__get_publisher_event_socket__ = MagicMock(return_value='tcp://bar.tld:9999')
        self.assertEqual('tcp://bar.tld:9999', lava.get_listener_url())

        lava.__get_publisher_event_socket__ = MagicMock(return_value='tcp://*:9999')
        self.assertEqual('tcp://foo.tld:9999', lava.get_listener_url())
