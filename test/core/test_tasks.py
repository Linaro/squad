import datetime
import json
import re


from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch, PropertyMock


from squad.core.models import Group, TestRun, Status, Build, ProjectStatus, SuiteVersion, PatchSource, KnownIssue, EmailTemplate
from squad.core.tasks import ParseTestRunData
from squad.core.tasks import PostProcessTestRun
from squad.core.tasks import RecordTestRunStatus
from squad.core.tasks import UpdateProjectStatus
from squad.core.tasks import ProcessTestRun
from squad.core.tasks import ProcessAllTestRuns
from squad.core.tasks import ReceiveTestRun
from squad.core.tasks import ValidateTestRun
from squad.core.tasks import CreateBuild
from squad.core.tasks import exceptions
from squad.core.tasks import cleanup_old_builds
from squad.core.tasks import cleanup_build
from squad.core.tasks import prepare_report


class CommonTestCase(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='mygroup')
        build = project.builds.create(version='1.0.0')
        self.environment = project.environments.create(slug='myenv')
        self.testrun = TestRun.objects.create(
            build=build,
            environment=self.environment,
            tests_file='{"test0": "fail", "foobar/test1": "pass", "onlytests/test1": "pass", "missing/mytest": "skip", "special/case.for[result/variants]": "pass"}',
            metrics_file='{"metric0": 1, "foobar/metric1": 10, "foobar/metric2": "10.5"}',
        )


class ParseTestRunDataTest(CommonTestCase):
    def test_basics(self):
        ParseTestRunData()(self.testrun)

        self.assertEqual(5, self.testrun.tests.count())
        self.assertEqual(3, self.testrun.metrics.count())

    def test_name_with_variant(self):
        ParseTestRunData()(self.testrun)
        special_case = self.testrun.tests.filter(name="case.for[result/variants]")
        self.assertEqual(1, special_case.count())

    def test_does_not_process_twice(self):
        ParseTestRunData()(self.testrun)
        ParseTestRunData()(self.testrun)

        self.assertEqual(5, self.testrun.tests.count())
        self.assertEqual(3, self.testrun.metrics.count())

    def test_creates_suite_metadata(self):
        ParseTestRunData()(self.testrun)
        suite = self.testrun.tests.last().suite
        metadata = suite.metadata
        self.assertEqual('suite', metadata.kind)

    def test_creates_test_metadata(self):
        ParseTestRunData()(self.testrun)
        test = self.testrun.tests.last()
        metadata = test.metadata
        self.assertIsNotNone(metadata)
        self.assertEqual(test.name, metadata.name)
        self.assertEqual(test.suite.slug, metadata.suite)
        self.assertEqual('test', metadata.kind)

    def test_creates_metric_metadata(self):
        ParseTestRunData()(self.testrun)
        self.testrun.refresh_from_db()
        metric = self.testrun.metrics.last()
        metadata = metric.metadata
        self.assertIsNotNone(metadata)
        self.assertEqual(metric.name, metadata.name)
        self.assertEqual(metric.suite.slug, metadata.suite)
        self.assertEqual('metric', metadata.kind)


class ProcessAllTestRunsTest(CommonTestCase):

    def test_processes_all(self):
        ProcessAllTestRuns()()
        self.assertEqual(5, self.testrun.tests.count())
        self.assertEqual(6, self.testrun.status.count())


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
        self.assertEqual(1, Status.objects.filter(suite__slug='special').count())

        status = Status.objects.filter(suite=None).last()
        self.assertEqual(status.tests_pass, 3)
        self.assertEqual(status.tests_fail, 1)
        self.assertEqual(status.tests_skip, 1)
        self.assertIsInstance(status.metrics_summary, float)

    def test_xfail(self):
        issue = KnownIssue.objects.create(
            title='some known issue',
            test_name='test0',
        )
        issue.environments.add(self.environment)
        ParseTestRunData()(self.testrun)
        RecordTestRunStatus()(self.testrun)

        global_status = Status.objects.filter(suite=None).last()
        suite_status = Status.objects.filter(suite__slug='/').last()
        self.assertEqual(global_status.tests_xfail, 1)
        self.assertEqual(suite_status.tests_xfail, 1)

    def test_xfail_with_suite_name(self):
        issue = KnownIssue.objects.create(
            title='some known issue',
            test_name='foobar/test1',
        )
        issue.environments.add(self.environment)
        self.testrun.tests_file = re.sub('"pass"', '"fail"', self.testrun.tests_file)
        self.testrun.save()
        ParseTestRunData()(self.testrun)
        RecordTestRunStatus()(self.testrun)

        global_status = Status.objects.filter(suite=None).last()
        suite_status = Status.objects.filter(suite__slug='foobar').last()
        self.assertEqual(global_status.tests_xfail, 1)
        self.assertEqual(suite_status.tests_xfail, 1)

    def test_does_not_process_twice(self):
        ParseTestRunData()(self.testrun)
        RecordTestRunStatus()(self.testrun)
        RecordTestRunStatus()(self.testrun)
        self.assertEqual(1, Status.objects.filter(suite=None).count())

    def test_suite_version_not_informed(self):
        ParseTestRunData()(self.testrun)
        RecordTestRunStatus()(self.testrun)

        self.assertEqual(0, SuiteVersion.objects.filter(suite__slug='/').count())
        self.assertEqual(0, SuiteVersion.objects.filter(suite__slug='foobar').count())
        self.assertEqual(0, SuiteVersion.objects.filter(suite__slug='onlytests').count())
        self.assertEqual(0, SuiteVersion.objects.filter(suite__slug='missing').count())
        self.assertEqual(0, SuiteVersion.objects.filter(suite__slug='special').count())
        self.assertIsNone(self.testrun.status.by_suite().first().suite_version)

    def set_suite_versions(self):
        self.testrun.metadata['suite_versions'] = {
            '/': '1',
            'foobar': '2',
            'onlytests': '3',
            'missing': '4',
            'special': '5',
        }
        self.testrun.save()

    def test_suite_version_informed(self):
        self.set_suite_versions()
        ParseTestRunData()(self.testrun)
        RecordTestRunStatus()(self.testrun)

        self.assertEqual(1, SuiteVersion.objects.filter(version='1', suite__slug='/').count())
        self.assertEqual(1, SuiteVersion.objects.filter(version='2', suite__slug='foobar').count())
        self.assertEqual(1, SuiteVersion.objects.filter(version='3', suite__slug='onlytests').count())
        self.assertEqual(1, SuiteVersion.objects.filter(version='4', suite__slug='missing').count())
        self.assertEqual(1, SuiteVersion.objects.filter(version='5', suite__slug='special').count())
        self.assertIsNotNone(self.testrun.status.by_suite().first().suite_version)


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
        self.assertEqual(5, self.testrun.tests.count())
        self.assertEqual(6, self.testrun.status.count())

    @patch('squad.core.tasks.PostProcessTestRun.__call__')
    def test_postprocess(self, postprocess):
        ProcessTestRun()(self.testrun)
        postprocess.assert_called_with(self.testrun)


class TestPostProcessTestRun(CommonTestCase):

    @patch('squad.plugins.example.Plugin.postprocess_testrun')
    def test_calls_enabled_plugin(self, plugin_method):
        project = self.testrun.build.project
        project.enabled_plugins_list = ['example']
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

    def test_update_project_status(self):
        receive = ReceiveTestRun(self.project)
        receive('199', 'myenv')
        testrun = TestRun.objects.last()
        self.assertEqual(1, ProjectStatus.objects.filter(build=testrun.build).count())

    @patch('squad.core.tasks.UpdateProjectStatus.__call__')
    def test_dont_update_project_status(self, UpdateProjectStatus):
        receive = ReceiveTestRun(self.project, update_project_status=False)
        receive('199', 'myenv')
        UpdateProjectStatus.assert_not_called()


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


class CreateBuildTest(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        self.project = group.projects.create(slug='mygroup')
        self.patch_source = PatchSource.objects.create(
            name='github',
            username='foo',
            url='https://github.com/',
            token='*********',
            implementation='example'
        )

    def test_basics(self):
        create_build = CreateBuild(self.project)
        baseline = create_build('0.0')
        build = create_build(
            version='1.0',
            patch_source=self.patch_source,
            patch_id='111',
            patch_baseline=baseline,
        )
        self.assertEqual(build.patch_source, self.patch_source)
        self.assertEqual(build.patch_id, '111')
        self.assertEqual(build.patch_baseline, baseline)

    @patch('squad.core.tasks.notify_patch_build_created')
    def test_notify_patch_source(self, notify_patch_build_created):
        create_build = CreateBuild(self.project)
        build = create_build('1.0', patch_source=self.patch_source, patch_id='111')
        notify_patch_build_created.delay.assert_called_with(build.id)

    @patch('squad.core.tasks.notify_patch_build_created')
    def test_dont_notify_without_patch_source(self, notify_patch_build_created):
        create_build = CreateBuild(self.project)
        create_build('1.0')  # no patch_source or patch_id
        notify_patch_build_created.delay.assert_not_called()


class CleanupOldBuildsTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject', data_retention_days=180)

    def create_build(self, version, created_at=None, project=None):
        if not project:
            project = self.project
        build = project.builds.create(version=version)
        if created_at:
            build.created_at = created_at  # override actual creation date
            build.save()
        return build

    @patch('squad.core.tasks.cleanup_build')
    def test_cleanup_old_builds(self, cleanup_build):
        seven_months_ago = timezone.now() - timezone.timedelta(210)
        old_build = self.create_build('1', seven_months_ago)
        self.create_build('2')  # new build, should be kept
        cleanup_old_builds()
        cleanup_build.delay.assert_called_once_with(old_build.id)

    @patch('squad.core.tasks.cleanup_build')
    def test_cleanup_old_builds_does_not_delete_builds_from_other_projects(self, cleanup_build):
        seven_months_ago = timezone.now() - timezone.timedelta(210)

        other_project = self.group.projects.create(slug='otherproject')
        self.create_build('1', created_at=seven_months_ago, project=other_project)
        cleanup_old_builds()
        cleanup_build.delay.assert_not_called()

    @patch('squad.core.tasks.cleanup_build')
    def test_cleanup_old_builds_respects_data_retention_policy(self, cleanup_build):
        build = self.create_build('1', timezone.now() - timezone.timedelta(90))
        cleanup_old_builds()
        cleanup_build.delay.assert_not_called()
        self.project.data_retention_days = 60
        self.project.save()
        cleanup_old_builds()
        cleanup_build.delay.assert_called_once_with(build.id)

    def test_cleanup_build(self):
        build_id = self.create_build('1').id
        self.assertTrue(self.project.builds.filter(id=build_id).exists())
        cleanup_build(build_id)
        self.assertFalse(self.project.builds.filter(id=build_id).exists())

    def test_cleanup_build_created_placeholder(self):
        build_id = self.create_build('1').id
        cleanup_build(build_id)
        self.assertTrue(self.project.build_placeholders.filter(version='1').exists())

    @patch('squad.core.tasks.cleanup_build')
    def test_no_cleanup_with_non_positive_data_retention_days(self, cleanup_build):
        self.project.data_retention_days = 0
        self.project.save()
        self.create_build('1', timezone.now() - timezone.timedelta(210))
        cleanup_old_builds()
        cleanup_build.delay.assert_not_called()

    @patch('squad.core.tasks.cleanup_build')
    def test_no_cleanup_when_build_has_keep_data_checked(self, cleanup_build):
        build = self.create_build('1', timezone.now() - timezone.timedelta(210))
        build.keep_data = True
        build.save()
        cleanup_old_builds()
        cleanup_build.delay.assert_not_called()


class PrepareDelayedReport(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        t = timezone.make_aware(datetime.datetime(2018, 10, 1, 1, 0, 0))
        self.build = self.project.builds.create(version='1', datetime=t)
        t2 = timezone.make_aware(datetime.datetime(2018, 10, 2, 1, 0, 0))
        self.build2 = self.project.builds.create(version='2', datetime=t2)
        self.environment = self.project.environments.create(slug='myenv')
        self.environment_a = self.project.environments.create(slug='env-a')
        self.testrun = self.build.test_runs.create(environment=self.environment, build=self.build)
        self.testrun2 = self.build2.test_runs.create(environment=self.environment, build=self.build2)
        self.testrun_a = self.build.test_runs.create(environment=self.environment_a, build=self.build)
        self.testrun2_a = self.build2.test_runs.create(environment=self.environment_a, build=self.build2)

        self.emailtemplate = EmailTemplate.objects.create(
            name="fooTemplate",
            subject="abc",
            plain_text="def",
        )
        self.validemailtemplate = EmailTemplate.objects.create(
            name="validTemplate",
            subject="subject",
            plain_text="{% if foo %}bar{% endif %}",
            html="{% if foo %}bar{% endif %}"
        )
        self.invalidemailtemplate = EmailTemplate.objects.create(
            name="invalidTemplate",
            subject="subject",
            plain_text="{% if foo %}bar",
            html="{% if foo %}bar"
        )

    def test_invalid_id(self):
        report = prepare_report(999)
        self.assertIsNone(report)

    def test_prepare_report(self):
        UpdateProjectStatus()(self.testrun)
        UpdateProjectStatus()(self.testrun2)
        report = self.build2.delayed_reports.create()
        prepared_report = prepare_report(report.pk)
        self.assertEqual(200, prepared_report.status_code)

    @patch('squad.core.tasks.notification.notify_delayed_report_email.delay')
    def test_email_notification(self, email_notification_mock):
        UpdateProjectStatus()(self.testrun)
        UpdateProjectStatus()(self.testrun2)
        report = self.build2.delayed_reports.create()
        report.email_recipient = "foo@bar.com"
        report.save()
        prepared_report = prepare_report(report.pk)
        self.assertEqual(200, prepared_report.status_code)
        email_notification_mock.assert_called_with(report.pk)

    @patch('squad.core.tasks.notification.notify_delayed_report_callback.delay')
    def test_callback_notification(self, callback_notification_mock):
        UpdateProjectStatus()(self.testrun)
        UpdateProjectStatus()(self.testrun2)
        report = self.build2.delayed_reports.create()
        report.callback = "http://foo.bar.com"
        report.save()
        prepared_report = prepare_report(report.pk)
        self.assertEqual(200, prepared_report.status_code)
        callback_notification_mock.assert_called_with(report.pk)
