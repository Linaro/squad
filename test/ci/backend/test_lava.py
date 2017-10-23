from django.core import mail
from django.test import TestCase
from mock import patch, MagicMock
import yaml
import xmlrpc


from squad.ci.models import Backend, TestJob
from squad.ci.backend.lava import Backend as LAVABackend
from squad.ci.exceptions import SubmissionIssue, TemporarySubmissionIssue
from squad.core.models import Group, Project


TEST_RESULTS = [
    {'duration': '',
     'id': '5089687',
     'job': '22505',
     'level': 'None',
     'logged': '2017-09-05 07:53:07.040871+00:00',
     'measurement': '29.7200000000',
     'metadata': {'case': 'auto-login-action',
                  'definition': 'lava',
                  'duration': '29.72',
                  'level': '4.5',
                  'result': 'pass'},
     'name': 'auto-login-action',
     'result': 'pass',
     'suite': 'lava',
     'timeout': '',
     'unit': 'seconds',
     'url': '/results/testcase/5089687'},
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

TEST_RESULTS_INFRA_FAILURE = [
    {
        'suite': 'lava',
        'name': 'job',
        'result': 'fail',
        'metadata': {
            'error_type': 'Infrastructure',
            'error_msg': 'foo-bar'
        },
    },
]

TEST_RESULTS_INFRA_FAILURE_RESUBMIT = [
    {
        'suite': 'lava',
        'name': 'job',
        'result': 'fail',
        'metadata': {
            'error_type': 'Infrastructure',
            'error_msg': 'Connection closed'
        },
    },
]

TEST_RESULTS_INFRA_FAILURE_RESUBMIT2 = [
    {
        'suite': 'lava',
        'name': 'job',
        'result': 'fail',
        'metadata': {
            'error_type': 'Infrastructure',
            'error_msg': 'auto-login-action timed out after 321 seconds'
        },
    },
]

JOB_METADATA = {
    'key_foo': 'value_foo',
    'key_bar': 'value_bar'
}


JOB_DEFINITION = {
    'job_name': 'job_foo',
    'metadata': JOB_METADATA,
    'device_type': 'device_foo'
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

JOB_DETAILS_CANCELED = {
    'is_pipeline': True,
    'status': 'Canceled',
    'id': 1234,
    'definition': yaml.dump(JOB_DEFINITION),
    'multinode_definition': ''
}

TEST_RESULTS_YAML = yaml.dump(TEST_RESULTS)
TEST_RESULTS_INFRA_FAILURE_YAML = yaml.dump(TEST_RESULTS_INFRA_FAILURE)
TEST_RESULTS_INFRA_FAILURE_RESUBMIT_YAML = yaml.dump(TEST_RESULTS_INFRA_FAILURE_RESUBMIT)
TEST_RESULTS_INFRA_FAILURE_RESUBMIT2_YAML = yaml.dump(TEST_RESULTS_INFRA_FAILURE_RESUBMIT2)


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
        self.group = Group.objects.create(
            name="group_foo"
        )
        self.project = Project.objects.create(
            name="project_foo",
            group=self.group,
        )

    def test_detect(self):
        impl = self.backend.get_implementation()
        self.assertIsInstance(impl, LAVABackend)

    @patch("squad.ci.backend.lava.Backend.__submit__", return_value='1234')
    def test_submit(self, __submit__):
        lava = LAVABackend(None)
        test_definition = "foo: 1\njob_name: bar"
        testjob = TestJob(
            definition=test_definition,
            backend=self.backend)
        self.assertEqual('1234', lava.submit(testjob))
        self.assertEqual('bar', testjob.name)
        __submit__.assert_called_with(test_definition)

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_YAML)
    def test_fetch_basics(self, get_results, get_details, get_logs):
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

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_YAML)
    def test_parse_results_metadata(self, get_results, get_details, get_logs):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)

        self.assertEqual(JOB_METADATA, metadata)

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_YAML)
    def test_parse_results(self, get_results, get_details, get_logs):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)

        self.assertEqual(len(results), 2)
        self.assertEqual(len(metrics), 2)
        self.assertEqual(10, metrics['DefinitionFoo/case_foo'])
        self.assertEqual('job_foo', testjob.name)

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_INFRA_FAILURE_YAML)
    def test_completed(self, get_results, get_details, get_logs):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend,
            target=self.project)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)
        self.assertFalse(completed)

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS_CANCELED)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_YAML)
    def test_canceled(self, get_results, get_details, get_logs):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend,
            target=self.project)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)
        self.assertFalse(completed)

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_INFRA_FAILURE_RESUBMIT_YAML)
    def test_automated_resubmit_email(self, get_results, get_details, get_logs):
        self.project.admin_subscriptions.create(email='foo@example.com')
        backend = MagicMock()
        backend.url = 'https://foo.tld/RPC2'
        lava = LAVABackend(backend)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend,
            target=self.project)
        resubmitted_job = TestJob(
            job_id='1235',
            backend=self.backend,
            target=self.project,
            resubmitted_count=1)
        resubmitted_job.save()
        lava.resubmit = MagicMock(return_value=resubmitted_job)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)
        lava.resubmit.assert_called()
        # there should be an admin email sent after resubmission
        self.assertEqual(1, len(mail.outbox))

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_INFRA_FAILURE_RESUBMIT_YAML)
    @patch("squad.ci.backend.lava.Backend.__resubmit__", return_value="1235")
    def test_automated_resubmit(self, lava_resubmit, get_results, get_details, get_logs):
        lava = LAVABackend(self.backend)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend,
            target=self.project)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)
        lava_resubmit.assert_called()
        new_test_job = TestJob.objects.all().last()
        self.assertEqual(1, new_test_job.resubmitted_count)
        self.assertFalse(testjob.can_resubmit)

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_INFRA_FAILURE_RESUBMIT2_YAML)
    @patch("squad.ci.backend.lava.Backend.__resubmit__", return_value="1235")
    def test_automated_resubmit2(self, lava_resubmit, get_results, get_details, get_logs):
        lava = LAVABackend(self.backend)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend,
            target=self.project)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)
        lava_resubmit.assert_called()
        new_test_job = TestJob.objects.all().last()
        self.assertEqual(1, new_test_job.resubmitted_count)
        self.assertFalse(testjob.can_resubmit)

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

    @patch('squad.ci.backend.lava.fetch')
    def test_receive_event(self, fetch):
        lava = LAVABackend(self.backend)
        testjob = TestJob.objects.create(
            backend=self.backend,
            target=self.project,
            build='1',
            environment='myenv',
            submitted=True,
            fetched=False,
            job_id='123',
            name="foo",
        )

        lava.receive_event('foo.com.testjob', {"job": '123', 'status': 'Complete'})
        # this is workaround to LAVA issues
        # it should be removed when LAVA bug is fixed
        fetch.apply_async.assert_called_with(args=[testjob.id], countdown=120)
        # proper solution below
        # fetch.fetch.assert_called_with(testjob.id)
        self.assertEqual('Complete', TestJob.objects.get(pk=testjob.id).job_status)

    def test_receive_event_no_testjob(self):
        backend = MagicMock()
        backend.url = 'https://foo.tld/RPC2'
        lava = LAVABackend(backend)

        # just not crashing is OK
        lava.receive_event('foo.com.testjob', {})

    def test_receive_event_wrong_topic(self):
        backend = MagicMock()
        backend.url = 'https://foo.tld/RPC2'
        lava = LAVABackend(backend)

        # just not crashing is OK
        lava.receive_event('foo.com.device', {'job': '123'})
