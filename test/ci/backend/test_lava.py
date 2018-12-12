from django.core import mail
from django.test import TestCase
from mock import patch, MagicMock
import os
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
    {'duration': '',
     'job': '12345',
     'level': 'None',
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


HTTP_400 = xmlrpc.client.Fault(400, 'Problem with submitted job data')
HTTP_503 = xmlrpc.client.Fault(503, 'Service Unavailable')
HTTP_401 = xmlrpc.client.ProtocolError('http://example.com', 401, 'Unauthorized', {})


class LavaTest(TestCase):

    def setUp(self):
        ci_infra_error_messages = [RESUBMIT_STRING, RESUBMIT_STRING2, RESUBMIT_STRING4]
        self.backend = Backend.objects.create(
            url='http://example.com/',
            username='myuser',
            token='mypassword',
            implementation_type='lava',
            backend_settings='{"CI_LAVA_INFRA_ERROR_MESSAGES": %s}' % ci_infra_error_messages,
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
        self.assertEqual('1234', lava.submit(testjob))
        self.assertEqual('bar', testjob.name)
        __submit__.assert_called_with(test_definition)

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
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
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results_metadata(self, get_results, get_details, get_logs):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)

        self.assertEqual(JOB_METADATA, metadata)

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS_NO_METADATA)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results_empty_metadata(self, get_results, get_details, get_logs):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)

        self.assertEqual({}, metadata)

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS_WITH_SUITE_VERSIONS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_WITH_SUITE_VERSIONS)
    def test_parse_results_metadata_with_suite_versions(self, get_results, get_details, get_logs):
        lava = LAVABackend(None)
        testjob = TestJob(
            job_id='1234',
            backend=self.backend)
        status, completed, metadata, results, metrics, logs = lava.fetch(testjob)

        self.assertEqual({"suite1": "1.0"}, metadata['suite_versions'])

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results_ignore_lava_suite_backend_settings(self, get_results, get_details, get_logs):
        self.backend.backend_settings = 'CI_LAVA_HANDLE_SUITE: true'
        lava = self.backend
        testjob = TestJob(
            job_id='1234',
            backend=self.backend,
            target=self.project,
            target_build=self.build)
        lava.fetch(testjob)
        results = testjob.testrun.tests
        metrics = testjob.testrun.metrics

        self.assertEqual(True, lava.get_implementation().settings.get('CI_LAVA_HANDLE_SUITE'))
        self.assertEqual(2, results.count())
        self.assertEqual(3, metrics.count())
        self.assertEqual(0, results.filter(name='device_foo').count())
        self.assertEqual(True, results.filter(name='validate').get().result)
        self.assertEqual(3, testjob.testrun.metrics.count())
        self.assertEqual(29.72, metrics.filter(name='auto-login-action').get().result)
        self.assertEqual(0.0, metrics.filter(name='power-off').get().result)
        self.assertEqual(10.0, metrics.filter(name='case_foo').get().result)

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results_ignore_lava_suite_project_settings(self, get_results, get_details, get_logs):
        self.project.project_settings = 'CI_LAVA_HANDLE_SUITE: true'
        lava = self.backend
        testjob = TestJob(
            job_id='1234',
            backend=self.backend,
            target=self.project,
            target_build=self.build)
        lava.fetch(testjob)
        results = testjob.testrun.tests
        metrics = testjob.testrun.metrics

        self.assertEqual(None, lava.get_implementation().settings.get('CI_LAVA_HANDLE_SUITE'))
        self.assertEqual(2, results.count())
        self.assertEqual(3, metrics.count())
        self.assertEqual(0, results.filter(name='device_foo').count())
        self.assertEqual(True, results.filter(name='validate').get().result)
        self.assertEqual(3, testjob.testrun.metrics.count())
        self.assertEqual(29.72, metrics.filter(name='auto-login-action').get().result)
        self.assertEqual(0.0, metrics.filter(name='power-off').get().result)
        self.assertEqual(10.0, metrics.filter(name='case_foo').get().result)

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
    def test_parse_results_ignore_lava_suite_project_settings_overwrites_backend(self, get_results, get_details, get_logs):
        self.backend.backend_settings = 'CI_LAVA_HANDLE_SUITE: true'
        lava = self.backend

        # Project settings has higher priority than backend settings
        self.project.project_settings = 'CI_LAVA_HANDLE_SUITE: false'
        testjob = TestJob(
            job_id='1234',
            backend=self.backend,
            target=self.project,
            target_build=self.build)
        lava.fetch(testjob)
        results = testjob.testrun.tests
        metrics = testjob.testrun.metrics

        self.assertEqual(True, lava.get_implementation().settings.get('CI_LAVA_HANDLE_SUITE'))
        self.assertEqual(2, results.count())
        self.assertEqual(2, metrics.count())
        self.assertEqual(1, results.filter(name='device_foo').count())
        self.assertEqual(0, results.filter(name='validate').count())
        self.assertEqual(2, testjob.testrun.metrics.count())
        self.assertEqual(0, metrics.filter(name='power-off').count())
        self.assertEqual(0, metrics.filter(name='auto-login-action').count())
        self.assertEqual(29.72, metrics.filter(name='time-device_foo').get().result)
        self.assertEqual(10.0, metrics.filter(name='case_foo').get().result)

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
    @patch("squad.ci.backend.lava.Backend.__get_job_details__", return_value=JOB_DETAILS)
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
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
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS_INFRA_FAILURE)
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
    @patch("squad.ci.backend.lava.Backend.__get_testjob_results_yaml__", return_value=TEST_RESULTS)
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

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
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

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
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

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
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

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
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

    @patch("squad.ci.backend.lava.Backend.__get_job_logs__", return_value="abc")
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
        log_data = open(os.path.join(os.path.dirname(__file__), 'example-lava-log.yaml')).read()
        log = lava.__parse_log__(log_data)
        self.assertIn("target message", log)
        self.assertNotIn("info message", log)
