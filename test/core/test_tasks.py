import json


from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch


from squad.core.models import Group, TestRun, Status, Build
from squad.core.tasks import ParseTestRunData
from squad.core.tasks import RecordTestRunStatus
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
            tests_file='{"test0": "fail", "foobar/test1": "pass", "onlytests/test1": "pass"}',
            metrics_file='{"metric0": 1, "foobar/metric1": 10}',
        )


class ParseTestRunDataTest(CommonTestCase):
    def test_basics(self):
        ParseTestRunData()(self.testrun)

        self.assertEqual(3, self.testrun.tests.count())
        self.assertEqual(2, self.testrun.metrics.count())

    def test_does_not_process_twice(self):
        ParseTestRunData()(self.testrun)
        ParseTestRunData()(self.testrun)

        self.assertEqual(3, self.testrun.tests.count())
        self.assertEqual(2, self.testrun.metrics.count())


class ProcessAllTestRunsTest(CommonTestCase):

    def test_processes_all(self):
        ProcessAllTestRuns()()
        self.assertEqual(3, self.testrun.tests.count())
        self.assertEqual(4, self.testrun.status.count())


class RecordTestRunStatusTest(CommonTestCase):

    def test_basics(self):
        ParseTestRunData()(self.testrun)
        RecordTestRunStatus()(self.testrun)

        # one for each suite + general
        self.assertEqual(1, Status.objects.filter(suite=None).count())
        self.assertEqual(1, Status.objects.filter(suite__slug='/').count())
        self.assertEqual(1, Status.objects.filter(suite__slug='foobar').count())
        self.assertEqual(1, Status.objects.filter(suite__slug='onlytests').count())

        status = Status.objects.filter(suite=None).last()
        self.assertEqual(status.tests_pass, 2)
        self.assertEqual(status.tests_fail, 1)
        self.assertIsInstance(status.metrics_summary, float)

    def test_does_not_process_twice(self):
        ParseTestRunData()(self.testrun)
        RecordTestRunStatus()(self.testrun)
        RecordTestRunStatus()(self.testrun)
        self.assertEqual(1, Status.objects.filter(suite=None).count())


class ProcessTestRunTest(CommonTestCase):

    def test_basics(self):
        ProcessTestRun()(self.testrun)
        self.assertEqual(3, self.testrun.tests.count())
        self.assertEqual(4, self.testrun.status.count())


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

        receive('199', 'myenv', metadata=json.dumps(metadata))
        testrun = TestRun.objects.last()

        self.assertEqual(today, testrun.datetime)
        self.assertEqual(metadata['job_id'], testrun.job_id)
        self.assertEqual(metadata['job_status'], testrun.job_status)
        self.assertEqual(metadata['job_url'], testrun.job_url)
        self.assertEqual(metadata['resubmit_url'], testrun.resubmit_url)
        self.assertEqual(metadata['build_url'], testrun.build_url)

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

        receive('199', 'myenv', metadata=json.dumps(metadata))
        build = Build.objects.get(version='199')

        self.assertEqual(yesterday, build.datetime)

    @patch('squad.core.tasks.ValidateTestRun.__call__')
    def test_should_validate_test_run(self, validator_mock):
        validator_mock.side_effect = RuntimeError('crashed')
        with self.assertRaises(RuntimeError):
            receive = ReceiveTestRun(self.project)
            receive('199', 'myenv')


class TestValidateTestRun(TestCase):

    # ~~~~~~~~~~~~ TESTS FOR METADATA ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def assertInvalidMetadata(self, metadata, exception=exceptions.InvalidMetadata):
        validate = ValidateTestRun()
        with self.assertRaises(exception):
            validate(metadata=metadata)

    def test_invalid_metadata_json(self):
        self.assertInvalidMetadata('{', exceptions.InvalidMetadataJSON)

    def test_invalid_metadata_type(self):
        self.assertInvalidMetadata('[]')

    def test_invalid_metadata_value(self):
        self.assertInvalidMetadata('{"foo" : [1,2,3]}')

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

    # ~~~~~~~~~~~~ TESTS FOR TESTS DATA ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def assertInvalidTests(self, tests, exception=exceptions.InvalidTestsData):
        validate = ValidateTestRun()
        with self.assertRaises(exception):
            validate(tests_file=tests)

    def test_invalid_tests_json(self):
        self.assertInvalidTests('{', exceptions.InvalidTestsDataJSON)

    def test_invalid_tests_type(self):
        self.assertInvalidTests('[]')

    def test_invalid_tests_value_type(self):
        self.assertInvalidTests('{"foo": 1}')

    def test_invalid_tests_string(self):
        self.assertInvalidTests('{"foo": "bar"}')
