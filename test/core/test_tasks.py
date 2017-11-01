import json


from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, PropertyMock


from squad.core.models import Group, TestRun, Status, Build, ProjectStatus
from squad.core.tasks import ParseTestRunData
from squad.core.tasks import PostProcessTestRun
from squad.core.tasks import RecordTestRunStatus
from squad.core.tasks import UpdateProjectStatus
from squad.core.tasks import ProcessTestRun
from squad.core.tasks import ProcessAllTestRuns
from squad.core.tasks import ReceiveTestRun
from squad.core.tasks import ValidateTestRun
from squad.core.tasks import exceptions


class CommonTestCase(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='mygroup')
        build = project.builds.create(version='1.0.0')
        env = project.environments.create(slug='myenv')
        self.testrun = TestRun.objects.create(
            build=build,
            environment=env,
            tests_file='{"test0": "fail", "foobar/test1": "pass", "onlytests/test1": "pass", "missing/mytest": "skip"}',
            metrics_file='{"metric0": 1, "foobar/metric1": 10, "foobar/metric2": "10.5"}',
        )


class ParseTestRunDataTest(CommonTestCase):
    def test_basics(self):
        ParseTestRunData()(self.testrun)

        self.assertEqual(4, self.testrun.tests.count())
        self.assertEqual(3, self.testrun.metrics.count())

    def test_does_not_process_twice(self):
        ParseTestRunData()(self.testrun)
        ParseTestRunData()(self.testrun)

        self.assertEqual(4, self.testrun.tests.count())
        self.assertEqual(3, self.testrun.metrics.count())


class ProcessAllTestRunsTest(CommonTestCase):

    def test_processes_all(self):
        ProcessAllTestRuns()()
        self.assertEqual(4, self.testrun.tests.count())
        self.assertEqual(5, self.testrun.status.count())


class RecordTestRunStatusTest(CommonTestCase):

    def test_basics(self):
        ParseTestRunData()(self.testrun)
        RecordTestRunStatus()(self.testrun)

        # one for each suite + general
        self.assertEqual(1, Status.objects.filter(suite=None).count())
        self.assertEqual(1, Status.objects.filter(suite__slug='/').count())
        self.assertEqual(1, Status.objects.filter(suite__slug='foobar').count())
        self.assertEqual(1, Status.objects.filter(suite__slug='onlytests').count())
        self.assertEqual(1, Status.objects.filter(suite__slug='missing').count())

        status = Status.objects.filter(suite=None).last()
        self.assertEqual(status.tests_pass, 2)
        self.assertEqual(status.tests_fail, 1)
        self.assertEqual(status.tests_skip, 1)
        self.assertIsInstance(status.metrics_summary, float)

    def test_does_not_process_twice(self):
        ParseTestRunData()(self.testrun)
        RecordTestRunStatus()(self.testrun)
        RecordTestRunStatus()(self.testrun)
        self.assertEqual(1, Status.objects.filter(suite=None).count())


class UpdateProjectStatusTest(CommonTestCase):

    @patch('squad.core.tasks.maybe_notify_project_status')
    def test_sends_notification(self, maybe_notify_project_status):
        ParseTestRunData()(self.testrun)
        RecordTestRunStatus()(self.testrun)
        UpdateProjectStatus()(self.testrun)

        status = ProjectStatus.objects.last()
        maybe_notify_project_status.delay.assert_called_with(status.id)


class ProcessTestRunTest(CommonTestCase):

    def test_basics(self):
        ProcessTestRun()(self.testrun)
        self.assertEqual(4, self.testrun.tests.count())
        self.assertEqual(5, self.testrun.status.count())
        self.assertEqual(1, ProjectStatus.objects.filter(build=self.testrun.build).count())

    @patch('squad.core.tasks.PostProcessTestRun.__call__')
    def test_postprocess(self, postprocess):
        ProcessTestRun()(self.testrun)
        postprocess.assert_called_with(self.testrun)


class TestPostProcessTestRun(CommonTestCase):

    @patch('squad.plugins.example.Plugin.postprocess_testrun')
    def test_calls_enabled_plugin(self, plugin_method):
        project = self.testrun.build.project
        project.enabled_plugins_list = 'example'
        project.save()
        PostProcessTestRun()(self.testrun)
        plugin_method.assert_called_with(self.testrun)


class ReceiveTestRunTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='mygroup')

    def test_metadata(self):
        receive = ReceiveTestRun(self.project)

        today = timezone.now()

        metadata = {
            "datetime": today.isoformat(),
            "job_id": '999',
            "job_status": 'pass',
            "job_url": 'https://example.com/jobs/999',
            "resubmit_url": 'https://example.com/jobs/999',
            "build_url": 'https://example/com/builds/777',
        }

        receive('199', 'myenv', metadata_file=json.dumps(metadata))
        testrun = TestRun.objects.last()

        self.assertEqual(today, testrun.datetime)
        self.assertEqual(metadata['job_id'], testrun.job_id)
        self.assertEqual(metadata['job_status'], testrun.job_status)
        self.assertEqual(metadata['job_url'], testrun.job_url)
        self.assertEqual(metadata['resubmit_url'], testrun.resubmit_url)
        self.assertEqual(metadata['build_url'], testrun.build_url)

    def test_metadata_non_string_values(self):
        receive = ReceiveTestRun(self.project)
        metadata_in = {
            'job_id': '12345',
            'number': 999,
            'version': 4.4,
            'list': [1, 2, 3],
            'object': {'1': 2},
        }

        receive('199', 'myenv', metadata_file=json.dumps(metadata_in))
        testrun = TestRun.objects.last()

        metadata = json.loads(testrun.metadata_file)
        self.assertEqual(metadata_in, metadata)

    def test_logfile(self):
        receive = ReceiveTestRun(self.project)
        metadata_in = {
            'job_id': '12345'
        }
        LOG_FILE_CONTENT = "abc"

        receive('199', 'myenv', metadata_file=json.dumps(metadata_in), log_file=LOG_FILE_CONTENT)
        testrun = TestRun.objects.last()

        self.assertEqual(LOG_FILE_CONTENT, testrun.log_file)

    def test_logfile_with_null_bytes(self):
        receive = ReceiveTestRun(self.project)
        metadata_in = {
            'job_id': '12345'
        }
        LOG_FILE_CONTENT = "ab\x00c"
        LOG_FILE_PROPER_CONTENT = "abc"

        receive('199', 'myenv', metadata_file=json.dumps(metadata_in), log_file=LOG_FILE_CONTENT)
        testrun = TestRun.objects.last()

        self.assertEqual(LOG_FILE_PROPER_CONTENT, testrun.log_file)

    def test_build_datetime(self):
        receive = ReceiveTestRun(self.project)

        yesterday = timezone.now() - relativedelta(days=7)

        metadata = {
            "datetime": yesterday.isoformat(),
            "job_id": '999',
            "job_status": 'pass',
            "job_url": 'https://example.com/jobs/999',
            "build_url": 'https://example/com/builds/777',
        }

        receive('199', 'myenv', metadata_file=json.dumps(metadata))
        build = Build.objects.get(version='199')

        self.assertEqual(yesterday, build.datetime)

    @patch('squad.core.tasks.ValidateTestRun.__call__')
    def test_should_validate_test_run(self, validator_mock):
        validator_mock.side_effect = RuntimeError('crashed')
        with self.assertRaises(RuntimeError):
            receive = ReceiveTestRun(self.project)
            receive('199', 'myenv')

    def test_test_result_is_not_pass_or_fail(self):
        receive = ReceiveTestRun(self.project)
        metadata = {
            "job_id": '999',
        }
        tests = {
            "test1": "pass",
            "test2": "fail",
            "test3": "skip",
        }

        receive('199', 'myenv', metadata_file=json.dumps(metadata), tests_file=json.dumps(tests))
        testrun = TestRun.objects.last()
        values = [t.result for t in testrun.tests.order_by('name')]
        self.assertEqual([True, False, None], values)

    def test_generate_job_id_when_not_present(self):
        receive = ReceiveTestRun(self.project)
        receive('199', 'myenv')
        testrun = TestRun.objects.last()
        self.assertIsNotNone(testrun.job_id)


class TestValidateTestRun(TestCase):

    # ~~~~~~~~~~~~ TESTS FOR METADATA ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def assertInvalidMetadata(self, metadata, exception=exceptions.InvalidMetadata):
        validate = ValidateTestRun()
        with self.assertRaises(exception):
            validate(metadata_file=metadata)

    def test_invalid_metadata_json(self):
        self.assertInvalidMetadata('{', exceptions.InvalidMetadataJSON)

    def test_invalid_metadata_type(self):
        self.assertInvalidMetadata('[]')

    def test_invalid_job_id(self):
        self.assertInvalidMetadata('{"job_id": "foo/bar"}')

    # ~~~~~~~~~~~~ TESTS FOR METRICS ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def assertInvalidMetrics(self, metrics, exception=exceptions.InvalidMetricsData):
        validate = ValidateTestRun()
        with self.assertRaises(exception):
            validate(metrics_file=metrics)

    def test_invalid_metrics_json(self):
        self.assertInvalidMetrics('{', exceptions.InvalidMetricsDataJSON)

    def test_invalid_metrics_type(self):
        self.assertInvalidMetrics('[]')

    def test_invalid_metrics_str_as_values(self):
        self.assertInvalidMetrics('{ "foo" : "bar"}')

    def test_invalid_metrics_list_of_str_as_values(self):
        self.assertInvalidMetrics('{ "foo" : ["bar"]}')

    def assertValidMetrics(self, metrics):
        validate = ValidateTestRun()
        validate(metrics_file=metrics)

    def test_number_as_string(self):
        self.assertValidMetrics('{"foo": "1.00000"}')

    # ~~~~~~~~~~~~ TESTS FOR TESTS DATA ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def assertInvalidTests(self, tests, exception=exceptions.InvalidTestsData):
        validate = ValidateTestRun()
        with self.assertRaises(exception):
            validate(tests_file=tests)

    def test_invalid_tests_json(self):
        self.assertInvalidTests('{', exceptions.InvalidTestsDataJSON)

    def test_invalid_tests_type(self):
        self.assertInvalidTests('[]')
