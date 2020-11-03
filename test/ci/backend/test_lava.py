from django.core import mail
from django.test import TestCase
from io import BytesIO
from test.mock import patch, MagicMock
import os
import requests
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
     'log_end_line': '4',
     'log_start_line': '1',
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
     'log_end_line': '4',
     'log_start_line': '5',
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
     'log_end_line': '5',
     'log_start_line': '4',
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
    {'duration': '',
     'job': '12345',
     'level': 'None',
     'log_end_line': '6',
     'log_start_line': '5',
     'logged': '2018-02-15 11:31:21.973616+00:00',
     'measurement': 'None',
     'metadata': {'case': 'validate',
                  'definition': 'lava',
                  'result': 'pass'},
     'name': 'validate',
     'result': 'pass',
     'suite': 'lava',
     'timeout': '',
     'unit': '',
     'url': '/results/testcase/12345'},
    {'duration': '',
     'job': '123456',
     'level': 'None',
     'log_end_line': '4',
     'log_start_line': '1',
     'logged': '2018-02-15 11:31:21.973616+00:00',
     'measurement': '0E-10',
     'metadata': {'case': 'power-off',
                  'definition': 'lava',
                  'result': 'pass'},
     'name': 'power-off',
     'result': 'pass',
     'suite': 'lava',
     'timeout': '',
     'unit': '',
     'url': '/results/testcase/123456'},
]

TEST_RESULTS_REST = [
    {'duration': '',
     'id': '5089687',
     'job': '22505',
     'level': 'None',
     'log_end_line': '4',
     'log_start_line': '1',
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
     'units': 'seconds',
     'url': '/results/testcase/5089687'},
    {'duration': '',
     'job': '1234',
     'level': 'None',
     'log_end_line': '4',
     'log_start_line': '5',
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
     'units': 'bottles',
     'url': '/results/1234/1_DefinitionFoo/case_foo'},
    {'duration': '',
     'job': '1234',
     'level': 'None',
     'log_end_line': '5',
     'log_start_line': '4',
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
     'units': '',
     'url': '/results/1234/1_DefinitionFoo/case_bar'},
    {'duration': '',
     'job': '12345',
     'level': 'None',
     'log_end_line': '6',
     'log_start_line': '5',
     'logged': '2018-02-15 11:31:21.973616+00:00',
     'measurement': 'None',
     'metadata': {'case': 'validate',
                  'definition': 'lava',
                  'result': 'pass'},
     'name': 'validate',
     'result': 'pass',
     'suite': 'lava',
     'timeout': '',
     'units': '',
     'url': '/results/testcase/12345'},
    {'duration': '',
     'job': '123456',
     'level': 'None',
     'log_end_line': '4',
     'log_start_line': '1',
     'logged': '2018-02-15 11:31:21.973616+00:00',
     'measurement': '0E-10',
     'metadata': {'case': 'power-off',
                  'definition': 'lava',
                  'result': 'pass'},
     'name': 'power-off',
     'result': 'pass',
     'suite': 'lava',
     'timeout': '',
     'units': '',
     'url': '/results/testcase/123456'},
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

TEST_RESULTS_INFRA_FAILURE_STR = [
    {
        'suite': 'lava',
        'name': 'job',
        'result': 'fail',
        'metadata': "{'error_type': 'Infrastructure', 'error_msg': 'foo-bar'}",
    },
]

TEST_RESULT_FAILURE_CUSTOM = "Testing, testing... 123"
TEST_RESULTS_INFRA_FAILURE_CUSTOM = [
    {
        'suite': 'lava',
        'name': 'job',
        'result': 'fail',
        'metadata': {
            'error_type': 'Infrastructure',
            'error_msg': TEST_RESULT_FAILURE_CUSTOM
        },
    },
]

TEST_RESULTS_WITH_JOB_INFRA_ERROR = TEST_RESULTS + TEST_RESULTS_INFRA_FAILURE

RESUBMIT_STRING = "Connection closed"
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

RESUBMIT_STRING2 = "auto-login-action timed out after [0-9]+ seconds"
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

TEST_RESULTS_INFRA_FAILURE_RESUBMIT3 = [
    {
        'suite': 'lava',
        'name': 'job',
        'result': 'fail',
        'metadata': {
            'error_type': 'Job',
            'error_msg': 'auto-login-action timed out after 321 seconds'
        },
    },
]

RESUBMIT_STRING4 = "adb device [A-Za-z0-9]+ lost!"
TEST_RESULTS_INFRA_FAILURE_RESUBMIT4 = [
    {
        'suite': 'lava',
        'name': 'job',
        'result': 'fail',
        'metadata': {
            'error_type': 'Test',
            'error_msg': 'adb device 16CA9F780038E32D lost!'
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

JOB_DEFINITION_NO_METADATA = {
    'job_name': 'job_foo',
    'device_type': 'device_foo'
}

JOB_DETAILS = {
    'status': 'Complete',
    'id': 1234,
    'definition': yaml.dump(JOB_DEFINITION),
    'multinode_definition': ''
}

JOB_DETAILS_INCOMPLETE = {
    'status': 'Incomplete',
    'id': 1234,
    'definition': yaml.dump(JOB_DEFINITION),
    'multinode_definition': ''
}

JOB_DETAILS_RUNNING = {
    'status': 'Running',
    'id': 1234,
    'definition': yaml.dump(JOB_DEFINITION),
    'multinode_definition': ''
}

JOB_DETAILS_CANCELED = {
    'status': 'Canceled',
    'id': 1234,
    'definition': yaml.dump(JOB_DEFINITION),
    'multinode_definition': ''
}

JOB_DETAILS_NO_METADATA = {
    'status': 'Complete',
    'id': 1234,
    'definition': yaml.dump(JOB_DEFINITION_NO_METADATA),
    'multinode_definition': ''
}

JOB_DETAILS_WITH_SUITE_VERSIONS = {
    'status': 'Complete',
    'id': 1234,
    'definition': yaml.dump({
        'job_name': 'job_foo',
        'metadata': {
            'suite1__version': "1.0",
        },
        'device_type': 'device_foo',
    }),
    'multinode_definition': ''
}

TEST_RESULTS_WITH_SUITE_VERSIONS = [
    {
        'duration': '',
        'id': '5089687',
        'job': '22505',
        'level': 'None',
        'logged': '2017-09-05 07:53:07.040871+00:00',
        'measurement': '29.7200000000',
        'metadata': {
            'case': 'test1',
            'definition': 'suite1',
            'duration': '29.72',
            'level': '4.5',
            'result': 'pass'
        },
        'name': 'test1',
        'result': 'pass',
        'suite': 'suite1',
        'timeout': '',
        'unit': 'seconds',
        'url': '/results/testcase/5089687'
    },
]

LOG_DATA = open(os.path.join(os.path.dirname(__file__), 'example-lava-log.yaml'), 'rb').read()
BROKEN_LOG_DATA = open(os.path.join(os.path.dirname(__file__), 'example-broken-log.yaml'), 'rb').read()

HTTP_400 = xmlrpc.client.Fault(400, 'Problem with submitted job data')
HTTP_500 = xmlrpc.client.Fault(500, 'Internal Server Error')
HTTP_503 = xmlrpc.client.Fault(503, 'Service Unavailable')
HTTP_401 = xmlrpc.client.ProtocolError('http://example.com', 401, 'Unauthorized', {})


class LavaTest(TestCase):

    def setUp(self):
        ci_infra_error_messages = [RESUBMIT_STRING, RESUBMIT_STRING2, RESUBMIT_STRING4]
        self.backend = Backend.objects.create(
            url='http://example.com/RPC2',
            username='myuser',
            token='mypassword',
            implementation_type='lava',
            backend_settings='{"CI_LAVA_INFRA_ERROR_MESSAGES": %s, "CI_LAVA_HANDLE_BOOT": true}' % ci_infra_error_messages,
        )
        self.group = Group.objects.create(
            name="group_foo"
        )
        self.project = Project.objects.create(
            name="project_foo",
            group=self.group,
        )
        self.build = self.project.builds.create(version='1')

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
        self.assertEqual(['1234'], lava.submit(testjob))
        self.assertEqual('bar', testjob.name)
        __submit__.assert_called_with(test_definition)

    @patch("requests.post", side_effect=requests.exceptions.Timeout)
    def test_submit_timeout(self, post):
        test_definition = "foo: 1\njob_name: bar"
        testjob = TestJob(
            definition=test_definition,
            backend=self.backend)
        self.assertRaises(requests.exceptions.Timeout, self.backend.submit, testjob)

    @patch("requests.post", side_effect=requests.exceptions.Timeout)
    def test_submit_rest_timeout(self, post):
        self.backend.url.replace("RPC2/", "api/v0.2/")
        test_definition = "foo: 1\njob_name: bar"
        testjob = TestJob(
            definition=test_definition,
            backend=self.backend)
        self.assertRaises(requests.exceptions.Timeout, self.backend.submit, testjob)

    @patch("squad.ci.backend.lava.Backend.__cancel_job__", return_value=True)
    def test_cancel(self, __cancel__):
        test_definition = "foo: 1\njob_name: bar"
        testjob = TestJob(
            definition=test_definition,
            submitted=True,
            job_id="12345",
            backend=self.backend)
        testjob.cancel()
        __cancel__.assert_called()

    @patch("requests.post", side_effect=requests.exceptions.Timeout)
    def test_cancel_timeout(self, __cancel__):
        test_definition = "foo: 1\njob_name: bar"
        testjob = TestJob(
            definition=test_definition,
            submitted=True,
            job_id="12345",
            backend=self.backend)
        self.assertRaises(requests.exceptions.Timeout, testjob.cancel)

    @patch("requests.post", side_effect=requests.exceptions.Timeout)
    def test_cancel_rest_timeout(self, __cancel__):
        self.backend.url.replace("RPC2/", "api/v0.2/")
        test_definition = "foo: 1\njob_name: bar"
        testjob = TestJob(
            definition=test_definition,
            submitted=True,
            job_id="12345",
            backend=self.backend)
        self.assertRaises(requests.exceptions.Timeout, testjob.cancel)

    @patch("squad.ci.backend.lava.Backend.__submit__", return_value=['1234.0', '1234.1'])
    def test_submit_multinode(self, __submit__):
        lava = LAVABackend(None)
        test_definition = "foo: 1\njob_name: bar"
        testjob = TestJob(
            definition=test_definition,
            backend=self.backend)
        self.assertEqual(['1234.0', '1234.1'], lava.submit(testjob))
        self.assertEqual('bar', testjob.name)
        __submit__.assert_called_with(test_definition)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_fetch_basics(self, get_results, get_details, test_log):
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

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results_metadata(self, get_results, get_details, test_log):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)

        self.assertEqual(JOB_METADATA, metadata)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS_NO_METADATA)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results_empty_metadata(self, get_results, get_details, test_log):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)

        self.assertEqual({}, metadata)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS_WITH_SUITE_VERSIONS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_WITH_SUITE_VERSIONS)
    def test_parse_results_metadata_with_suite_versions(self, get_results, get_details, test_log):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)

        self.assertEqual({"suite1": "1.0"}, metadata['suite_versions'])

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results_ignore_lava_suite_backend_settings(self, get_results, get_details, test_log):
        self.backend.backend_settings = 'CI_LAVA_HANDLE_SUITE: true'
        self.backend.save()
        lava = self.backend
        testjob = TestJob.objects.create(
            job_id='1234',
            backend=self.backend,
            target=self.project,
            target_build=self.build)
        lava.fetch(testjob.id)
        testjob.refresh_from_db()
        results = testjob.testrun.tests
        metrics = testjob.testrun.metrics

        self.assertEqual(True, lava.get_implementation().settings.get('CI_LAVA_HANDLE_SUITE'))
        self.assertEqual(2, results.count())
        self.assertEqual(3, metrics.count())
        self.assertEqual(0, results.filter(metadata__name='device_foo').count())
        self.assertEqual(True, results.filter(metadata__name='validate').get().result)
        self.assertEqual(3, testjob.testrun.metrics.count())
        self.assertEqual(29.72, metrics.filter(name='auto-login-action').get().result)
        self.assertEqual(0.0, metrics.filter(name='power-off').get().result)
        self.assertEqual(10.0, metrics.filter(name='case_foo').get().result)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results_ignore_lava_suite_project_settings(self, get_results, get_details, test_log):
        self.project.project_settings = 'CI_LAVA_HANDLE_SUITE: true'
        self.project.save()
        lava = self.backend
        testjob = TestJob.objects.create(
            job_id='1234',
            backend=self.backend,
            target=self.project,
            target_build=self.build)
        lava.fetch(testjob.id)
        testjob.refresh_from_db()
        results = testjob.testrun.tests
        metrics = testjob.testrun.metrics
        self.assertEqual(None, lava.get_implementation().settings.get('CI_LAVA_HANDLE_SUITE'))
        self.assertEqual(2, results.count())
        self.assertEqual(3, metrics.count())
        self.assertEqual(0, results.filter(metadata__name='device_foo').count())
        self.assertEqual(True, results.filter(metadata__name='validate').get().result)
        self.assertEqual(3, testjob.testrun.metrics.count())
        self.assertEqual(29.72, metrics.filter(name='auto-login-action').get().result)
        self.assertEqual(0.0, metrics.filter(name='power-off').get().result)
        self.assertEqual(10.0, metrics.filter(name='case_foo').get().result)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results_ignore_lava_suite_empty_project_settings(self, get_results, get_details, test_log):
        self.project.project_settings = ''
        lava = self.backend
        testjob = TestJob.objects.create(
            job_id='1234',
            backend=self.backend,
            target=self.project,
            target_build=self.build)
        lava.fetch(testjob.id)
        testjob.refresh_from_db()
        results = testjob.testrun.tests
        metrics = testjob.testrun.metrics

        self.assertEqual(None, lava.get_implementation().settings.get('CI_LAVA_HANDLE_SUITE'))
        self.assertEqual(2, results.count())
        self.assertEqual(2, metrics.count())
        self.assertEqual(1, results.filter(metadata__name='device_foo').count())
        self.assertEqual(0, results.filter(metadata__name='validate').count())
        self.assertEqual(2, testjob.testrun.metrics.count())
        self.assertEqual(0, metrics.filter(name='power-off').count())
        self.assertEqual(0, metrics.filter(name='auto-login-action').count())
        self.assertEqual(29.72, metrics.filter(name='time-device_foo').get().result)
        self.assertEqual(10.0, metrics.filter(name='case_foo').get().result)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results_ignore_lava_suite_project_settings_overwrites_backend(self, get_results, get_details, test_log):
        self.backend.backend_settings = 'CI_LAVA_HANDLE_SUITE: true'
        self.backend.save()
        lava = self.backend

        # Project settings has higher priority than backend settings
        self.project.project_settings = 'CI_LAVA_HANDLE_SUITE: false'
        self.project.save()
        testjob = TestJob.objects.create(
            job_id='1234',
            backend=self.backend,
            target=self.project,
            target_build=self.build)
        lava.fetch(testjob.id)
        testjob.refresh_from_db()
        results = testjob.testrun.tests
        metrics = testjob.testrun.metrics

        self.assertEqual(True, lava.get_implementation().settings.get('CI_LAVA_HANDLE_SUITE'))
        self.assertEqual(1, results.count())
        self.assertEqual(1, metrics.count())
        self.assertEqual(0, results.filter(metadata__name='device_foo').count())
        self.assertEqual(0, results.filter(metadata__name='validate').count())
        self.assertEqual(1, testjob.testrun.metrics.count())
        self.assertEqual(0, metrics.filter(name='power-off').count())
        self.assertEqual(0, metrics.filter(name='auto-login-action').count())
        self.assertEqual(0, metrics.filter(name='time-device_foo').count())
        self.assertEqual(10.0, metrics.filter(name='case_foo').get().result)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results_ignore_lava_boot(self, get_results, get_details, download_test_log):
        self.backend.backend_settings = ''
        lava = self.backend

        testjob = TestJob.objects.create(
            job_id='1234',
            backend=self.backend,
            target=self.project,
            target_build=self.build)
        lava.fetch(testjob.id)
        testjob.refresh_from_db()
        results = testjob.testrun.tests
        metrics = testjob.testrun.metrics

        self.assertEqual(1, results.count())
        self.assertEqual(1, metrics.count())
        self.assertEqual(0, results.filter(metadata__name='device_foo').count())
        self.assertEqual(0, metrics.filter(name='time-device_foo').count())
        self.assertEqual(1, results.filter(metadata__name='case_bar').count())
        self.assertEqual(1, metrics.filter(name='case_foo').count())
        self.assertEqual(10.0, metrics.filter(name='case_foo').get().result)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS_INCOMPLETE)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_WITH_JOB_INFRA_ERROR)
    def test_parse_results_ignore_infra_errors(self, get_results, get_details, download_test_log):
        self.backend.backend_settings = '{"CI_LAVA_WORK_AROUND_INFRA_ERRORS": true}'
        lava = self.backend

        testjob = TestJob.objects.create(
            job_id='1234',
            backend=self.backend,
            target=self.project,
            target_build=self.build)
        lava.fetch(testjob.id)
        testjob.refresh_from_db()
        results = testjob.testrun.tests
        metrics = testjob.testrun.metrics

        self.assertEqual(True, testjob.testrun.completed)
        self.assertEqual(1, results.count())
        self.assertEqual(1, metrics.count())
        self.assertEqual(0, results.filter(metadata__name='device_foo').count())
        self.assertEqual(0, metrics.filter(name='time-device_foo').count())
        self.assertEqual(1, results.filter(metadata__name='case_bar').count())
        self.assertEqual(1, metrics.filter(name='case_foo').count())
        self.assertEqual(10.0, metrics.filter(name='case_foo').get().result)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS_INCOMPLETE)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_WITH_JOB_INFRA_ERROR)
    def test_parse_results_dont_ignore_infra_errors(self, get_results, get_details, download_test_log):
        self.backend.backend_settings = '{"CI_LAVA_WORK_AROUND_INFRA_ERRORS": false}'
        lava = self.backend

        testjob = TestJob.objects.create(
            job_id='1234',
            backend=self.backend,
            target=self.project,
            target_build=self.build)
        lava.fetch(testjob.id)
        testjob.refresh_from_db()
        results = testjob.testrun.tests
        metrics = testjob.testrun.metrics

        self.assertEqual(False, testjob.testrun.completed)
        self.assertEqual(0, results.count())
        self.assertEqual(0, metrics.count())

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results_handle_lava_suite_and_ignore_lava_boot(self, get_results, get_details, download_test_log):
        self.backend.backend_settings = '{"CI_LAVA_HANDLE_SUITE": true, "CI_LAVA_HANDLE_BOOT": false}'
        self.backend.save()
        lava = self.backend
        testjob = TestJob.objects.create(
            job_id='1234',
            backend=self.backend,
            target=self.project,
            target_build=self.build)
        lava.fetch(testjob.id)
        testjob.refresh_from_db()
        results = testjob.testrun.tests
        metrics = testjob.testrun.metrics
        self.assertEqual(True, lava.get_implementation().settings.get('CI_LAVA_HANDLE_SUITE'))
        self.assertEqual(False, lava.get_implementation().settings.get('CI_LAVA_HANDLE_BOOT'))
        self.assertEqual(2, results.count())
        self.assertEqual(3, metrics.count())
        self.assertEqual(0, results.filter(metadata__name='device_foo').count())
        self.assertEqual(True, results.filter(metadata__name='validate').get().result)
        self.assertEqual(29.72, metrics.filter(name='auto-login-action').get().result)
        self.assertEqual(0.0, metrics.filter(name='power-off').get().result)
        self.assertEqual(10.0, metrics.filter(name='case_foo').get().result)
        self.assertEqual(0, metrics.filter(name='time-device_foo').count())

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results(self, get_results, get_details, download_test_log):
        lava = LAVABackend(self.backend)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)

        self.assertEqual(len(results), 2)
        self.assertIn('log', results['DefinitionFoo/case_bar'].keys())
        self.assertEqual(len(metrics), 2)
        self.assertEqual(10, metrics['DefinitionFoo/case_foo']["value"])
        self.assertEqual('job_foo', testjob.name)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_REST)
    def test_parse_results_rest(self, get_results, get_details, download_test_log):
        # this test is a workaround of LAVA bug
        # https://git.lavasoftware.org/lava/lava/-/issues/449
        lava = LAVABackend(self.backend)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)

        self.assertEqual(len(results), 2)
        self.assertIn('log', results['DefinitionFoo/case_bar'].keys())
        self.assertEqual(len(metrics), 2)
        self.assertEqual(10, metrics['DefinitionFoo/case_foo']["value"])
        self.assertEqual('job_foo', testjob.name)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results_clone_measurements(self, get_results, get_details, test_log):
        self.backend.backend_settings = '{"CI_LAVA_CLONE_MEASUREMENTS": true, "CI_LAVA_HANDLE_BOOT": true}'

        # Project settings has higher priority than backend settings
        self.project.project_settings = 'CI_LAVA_CLONE_MEASUREMENTS: true'

        lava = LAVABackend(self.backend)
        testjob = TestJob(
            job_id='1235',
            backend=self.backend,
            target=self.project,
            target_build=self.build,
            environment="foo_env")
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)

        self.assertEqual(len(results), 3)
        self.assertEqual(len(metrics), 2)
        self.assertEqual(10, metrics['DefinitionFoo/case_foo']["value"])
        self.assertEqual('job_foo', testjob.name)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_INFRA_FAILURE)
    def test_completed(self, get_results, get_details, get_logs):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend,
            target=self.project)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)
        self.assertFalse(completed)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_INFRA_FAILURE_STR)
    def test_incomplete_string_results_metadata(self, get_results, get_details, get_logs):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend,
            target=self.project)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)
        self.assertFalse(completed)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS_CANCELED)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_canceled(self, get_results, get_details, get_logs):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend,
            target=self.project)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)
        self.assertFalse(completed)

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_INFRA_FAILURE_RESUBMIT)
    def test_automated_resubmit_email(self, get_results, get_details, get_logs):
        self.project.admin_subscriptions.create(email='foo@example.com')
        lava = LAVABackend(self.backend)
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

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_INFRA_FAILURE_RESUBMIT)
    def test_automated_dont_resubmit_email(self, get_results, get_details, get_logs):
        self.project.admin_subscriptions.create(email='foo@example.com')
        lava = LAVABackend(self.backend)
        # update lava backend settings in place
        lava.settings['CI_LAVA_SEND_ADMIN_EMAIL'] = False
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
        # there should not be an admin email sent after resubmission
        self.assertEqual(0, len(mail.outbox))

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_INFRA_FAILURE_RESUBMIT)
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

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_INFRA_FAILURE_CUSTOM)
    @patch("squad.ci.backend.lava.Backend.__resubmit__", return_value="1235")
    def test_automated_resubmit_with_project_settings(self, lava_resubmit, get_results, get_details, get_logs):
        self.project.project_settings = yaml.dump({'CI_LAVA_INFRA_ERROR_MESSAGES': [TEST_RESULT_FAILURE_CUSTOM]})
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

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_INFRA_FAILURE_RESUBMIT2)
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

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_INFRA_FAILURE_RESUBMIT3)
    @patch("squad.ci.backend.lava.Backend.__resubmit__", return_value="1235")
    def test_automated_resubmit3(self, lava_resubmit, get_results, get_details, get_logs):
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

    @patch("squad.ci.backend.lava.Backend.__download_full_log__", return_value=LOG_DATA)
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_INFRA_FAILURE_RESUBMIT4)
    @patch("squad.ci.backend.lava.Backend.__resubmit__", return_value="1235")
    def test_automated_resubmit4(self, lava_resubmit, get_results, get_details, get_logs):
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
            target_build=self.build,
            environment='myenv',
            submitted=True,
            fetched=False,
            job_id='123',
            name="foo",
        )

        lava.receive_event('foo.com.testjob', {"job": '123', 'state': 'Finished', 'health': 'Complete'})
        fetch.apply_async.assert_called_with(args=[testjob.id])
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

    @patch('squad.ci.backend.lava.fetch')
    def test_receive_event_no_status(self, fetch):
        lava = LAVABackend(self.backend)
        testjob = TestJob.objects.create(
            backend=self.backend,
            target=self.project,
            target_build=self.build,
            environment='myenv',
            submitted=True,
            fetched=False,
            job_id='123',
            name="foo",
        )

        lava.receive_event('foo.com.testjob', {"job": '123'})
        self.assertEqual('Unknown', TestJob.objects.get(pk=testjob.id).job_status)

    def test_lava_log_parsing(self):
        lava = LAVABackend(self.backend)
        log_data = BytesIO(LOG_DATA)
        log = lava.__parse_log__(log_data)
        self.assertIn("target message", log)
        self.assertNotIn("info message", log)

    @patch('requests.get')
    def test_lava_log_download(self, requests_get):
        lava1 = LAVABackend(self.backend)
        requests_get.side_effect = requests.exceptions.ChunkedEncodingError("Connection closed")
        log = lava1.__download_full_log__(999)
        requests_get.assert_called()
        self.assertEqual(b'', log)

    @patch('requests.get')
    def test_lava_log_download_rest(self, requests_get):
        # check REST API path
        self.backend.url.replace("RPC2/", "api/v0.2/")
        lava2 = LAVABackend(self.backend)
        requests_get.side_effect = requests.exceptions.ChunkedEncodingError("Connection closed")
        log = lava2.__download_full_log__(999)
        requests_get.assert_called()
        self.assertEqual(b'', log)

    def test_broken_lava_log_parsing(self):
        lava = LAVABackend(self.backend)
        log_data = BytesIO(BROKEN_LOG_DATA)
        log = lava.__parse_log__(log_data)
        self.assertEqual(0, len(log))

    def test_empty_lava_log_parsing(self):
        lava = LAVABackend(self.backend)
        log_data = BytesIO()
        log = lava.__parse_log__(log_data)
        self.assertEqual(0, len(log))

    def test_test_log_unicode_error(self):
        lava = LAVABackend(self.backend)
        log_data = BytesIO(b'a non-decodable unicode char: \xb1\n')
        test_log = lava.__download_test_log__(log_data, 1, 3)
        self.assertIn("a non-decodable unicode char:", test_log)

    @patch("squad.ci.backend.lava.Backend.__resubmit__", side_effect=HTTP_500)
    def test_resubmit_deleted_job(self, __resubmit__):
        lava = LAVABackend(None)
        test_definition = "foo: 1\njob_name: bar"
        testjob = TestJob(
            definition=test_definition,
            backend=self.backend,
            job_id='9999',
        )
        with self.assertRaises(SubmissionIssue):
            lava.resubmit(testjob)
