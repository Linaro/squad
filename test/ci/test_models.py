from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.test import TestCase
from test.mock import patch, MagicMock
import yaml


from squad.core import models as core_models


from squad.ci import models
from squad.ci.backend.null import Backend
from squad.ci.exceptions import SubmissionIssue


class BackendTest(TestCase):

    def test_basics(self):
        models.Backend(
            url='http://example.com',
            username='foobar',
            token='mypassword'
        )

    def test_implementation(self):
        backend = models.Backend()
        impl = backend.get_implementation()
        self.assertIsInstance(impl, Backend)


NOW = timezone.now()


class BackendTestBase(TestCase):

    def setUp(self):
        self.group = core_models.Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.backend = models.Backend.objects.create()
        self.build = self.project.builds.create(version='1')

    def create_test_job(self, **attrs):
        return self.backend.test_jobs.create(target=self.project, target_build=self.build, **attrs)


class BackendPollTest(BackendTestBase):

    def test_poll(self):
        test_job = self.create_test_job(submitted=True)
        jobs = list(self.backend.poll())
        self.assertEqual([test_job], jobs)

    def test_poll_enabled(self):
        self.create_test_job(submitted=True)
        self.backend.poll_enabled = False
        jobs = list(self.backend.poll())
        self.assertEqual([], jobs)

    def test_poll_wont_fetch_non_submitted_job(self):
        self.create_test_job(submitted=False)
        jobs = list(self.backend.poll())
        self.assertEqual(jobs, [])

    def test_poll_wont_fetch_job_previouly_fetched(self):
        self.create_test_job(submitted=True, fetched=True)
        jobs = list(self.backend.poll())
        self.assertEqual(jobs, [])

    def test_poll_wont_fetch_before_poll_interval(self):
        self.create_test_job(submitted=True, last_fetch_attempt=NOW)
        jobs = list(self.backend.poll())
        self.assertEqual(jobs, [])

    def test_poll_will_fetch_after_poll_interval(self):
        past = timezone.now() - relativedelta(minutes=self.backend.poll_interval + 1)
        test_job = self.create_test_job(submitted=True, last_fetch_attempt=past)
        jobs = list(self.backend.poll())
        self.assertEqual([test_job], jobs)

    def test_poll_gives_up_eventually(self):
        self.create_test_job(submitted=True, fetch_attempts=self.backend.max_fetch_attempts + 1)
        jobs = list(self.backend.poll())
        self.assertEqual([], jobs)


class BackendFetchTest(BackendTestBase):

    @patch("squad.ci.backend.null.Backend.fetch")
    def test_fetch_skips_already_fetched(self, fetch):
        test_job = self.create_test_job(submitted=True, fetched=True)
        self.backend.fetch(test_job.id)

        fetch.assert_not_called()

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_fetch(self, get_implementation, __now__):
        impl = MagicMock()
        impl.fetch = MagicMock(return_value=None)
        get_implementation.return_value = impl

        test_job = self.create_test_job()
        self.backend.fetch(test_job.id)

        test_job.refresh_from_db()
        self.assertEqual(NOW, test_job.last_fetch_attempt)
        self.assertFalse(test_job.fetched)

        get_implementation.assert_called()
        impl.fetch.assert_called()

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_fetch_creates_testrun(self, get_implementation, __now__):
        metadata = {"foo": "bar"}
        tests = {"foo": "pass"}
        metrics = {"bar": {"value": 1, "unit": ""}}
        results = ('Complete', True, metadata, tests, metrics, "abc")

        project_status = self.build.status
        tests_pass_so_far = project_status.tests_pass

        impl = MagicMock()
        impl.fetch = MagicMock(return_value=results)
        impl.job_url = MagicMock(return_value="http://www.example.com")
        get_implementation.return_value = impl

        test_job = self.create_test_job(
            backend=self.backend,
            definition='foo: 1',
            environment='myenv',
            job_id='999',
        )

        self.backend.fetch(test_job.id)

        # should not crash
        test_run = core_models.TestRun.objects.get(
            build__project=self.project,
            environment__slug='myenv',
            build__version='1',
            job_id='999',
            job_status='Complete',
            completed=True,
        )
        self.assertEqual(
            1,
            core_models.Test.objects.filter(
                test_run=test_run,
                metadata__name="foo",
                result=True,
            ).count()
        )
        self.assertEqual(
            1,
            core_models.Metric.objects.filter(
                test_run=test_run,
                metadata__name="bar",
                result=1,
            ).count()
        )
        project_status.refresh_from_db()
        self.assertEqual(project_status.tests_pass, tests_pass_so_far + 1)
        test_job.refresh_from_db()
        self.assertTrue(test_job.fetched)

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_fetch_sets_fetched_on_invalid_metadata(self, get_implementation, __now__):
        metadata = {"foo": "bar"}
        tests = {"foo": "pass"}
        metrics = {"bar": {"value": 1, "unit": "nuggets"}}
        results = ('Complete', True, metadata, tests, metrics, "abc")

        impl = MagicMock()
        impl.fetch = MagicMock(return_value=results)
        impl.job_url = MagicMock(return_value="http://www.example.com")
        get_implementation.return_value = impl

        environment = self.project.environments.create(slug='myenv')
        self.build.test_runs.create(
            environment=environment,
            job_id='999',
            job_status='Complete',
            completed=True,
        )

        test_job = self.create_test_job(
            backend=self.backend,
            definition='foo: 1',
            environment='myenv',
            job_id='999',
        )

        self.backend.fetch(test_job.id)

        test_job.refresh_from_db()
        self.assertTrue(test_job.fetched)
        self.assertIsNone(test_job.failure)

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_fetch_with_empty_results(self, get_implementation, __now__):
        metadata = {"foo": "bar"}
        tests = {}
        metrics = {}
        results = ('Complete', True, metadata, tests, metrics, "abc")

        impl = MagicMock()
        impl.fetch = MagicMock(return_value=results)
        impl.job_url = MagicMock(return_value="http://www.example.com")
        get_implementation.return_value = impl

        test_job = self.create_test_job(
            backend=self.backend,
            definition='foo: 1',
            environment='myenv',
            job_id='999',
        )

        self.backend.fetch(test_job.id)

        # should not crash
        test_run = core_models.TestRun.objects.get(
            build__project=self.project,
            environment__slug='myenv',
            build__version='1',
            job_id='999',
            job_status='Complete',
        )
        test_job.refresh_from_db()
        self.assertTrue(test_job.can_resubmit)
        self.assertFalse(test_run.completed)

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_fetch_with_only_results(self, get_implementation, __now__):
        metadata = {"foo": "bar"}
        tests = {"foo": "pass"}
        metrics = {}
        results = ('Complete', True, metadata, tests, metrics, "abc")

        impl = MagicMock()
        impl.fetch = MagicMock(return_value=results)
        impl.job_url = MagicMock(return_value="http://www.example.com")
        get_implementation.return_value = impl

        test_job = self.create_test_job(
            backend=self.backend,
            definition='foo: 1',
            environment='myenv',
            job_id='999',
        )

        self.backend.fetch(test_job.id)

        # should not crash
        test_run = core_models.TestRun.objects.get(
            build__project=self.project,
            environment__slug='myenv',
            build__version='1',
            job_id='999',
            job_status='Complete',
        )
        test_job.refresh_from_db()
        self.assertFalse(test_job.can_resubmit)
        self.assertTrue(test_run.completed)

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_fetch_with_only_metrics(self, get_implementation, __now__):
        metadata = {"foo": "bar"}
        tests = {}
        metrics = {"foo": {"value": 10, "unit": "boxes"}}
        results = ('Complete', True, metadata, tests, metrics, "abc")

        impl = MagicMock()
        impl.fetch = MagicMock(return_value=results)
        impl.job_url = MagicMock(return_value="http://www.example.com")
        get_implementation.return_value = impl

        test_job = self.create_test_job(
            backend=self.backend,
            definition='foo: 1',
            environment='myenv',
            job_id='999',
        )

        self.backend.fetch(test_job.id)

        # should not crash
        test_run = core_models.TestRun.objects.get(
            build__project=self.project,
            environment__slug='myenv',
            build__version='1',
            job_id='999',
            job_status='Complete',
        )
        test_job.refresh_from_db()
        self.assertFalse(test_job.can_resubmit)
        self.assertTrue(test_run.completed)

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_create_testrun_job_url(self, get_implementation, __now__):
        metadata = {"foo": "bar"}
        tests = {"foo": "pass"}
        metrics = {"bar": {"value": 1, "unit": "donuts"}}
        results = ('Complete', True, metadata, tests, metrics, "abc")
        test_job_url = "http://www.example.com"

        impl = MagicMock()
        impl.fetch = MagicMock(return_value=results)
        impl.job_url = MagicMock(return_value=test_job_url)
        get_implementation.return_value = impl

        test_job = self.create_test_job(
            backend=self.backend,
            definition='foo: 1',
            environment='myenv',
            job_id='999',
        )

        self.backend.fetch(test_job.id)

        # should not crash
        test_run = core_models.TestRun.objects.get(
            build__project=self.project,
            environment__slug='myenv',
            build__version='1',
            job_id='999',
            job_status='Complete',
            completed=True,
        )
        test_job.refresh_from_db()
        self.assertEqual(test_run.job_url, test_job_url)

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_fetch_ignores_results_from_incomplete_job(self, get_implementation, __now__):
        metadata = {"foo": "bar"}
        tests = {"foo": "pass"}
        metrics = {"bar": {"value": 1, "unit": ""}}
        results = ('Incomplete', False, metadata, tests, metrics, "abc")
        #                        ^^^^^ job resulted in an infra failure

        impl = MagicMock()
        impl.fetch = MagicMock(return_value=results)
        impl.job_url = MagicMock(return_value="http://www.example.com")
        get_implementation.return_value = impl

        test_job = self.create_test_job(
            backend=self.backend,
            definition='foo: 1',
            environment='myenv',
            job_id='999',
        )

        self.backend.fetch(test_job.id)
        test_job.refresh_from_db()
        self.assertTrue(test_job.can_resubmit)

        # should not crash
        testrun = core_models.TestRun.objects.get(
            build__project=self.project,
            environment__slug='myenv',
            build__version='1',
            job_id='999',
            job_status='Incomplete',
            completed=False,  # even if results are not empty
        )

        # no results get recorded
        self.assertEqual(0, testrun.tests.count())
        self.assertEqual(0, testrun.metrics.count())

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_fetch_sets_testjob_can_resubmit_and_testrun_completed2(self, get_implementation, __now__):
        metadata = {"foo": "bar"}
        tests = {}
        metrics = {}
        results = ('Incomplete', False, metadata, tests, metrics, "abc")
        #                        ^^^^^ job resulted in an infra failure

        impl = MagicMock()
        impl.fetch = MagicMock(return_value=results)
        impl.job_url = MagicMock(return_value="http://www.example.com")
        get_implementation.return_value = impl

        test_job = self.create_test_job(
            backend=self.backend,
            definition='foo: 1',
            environment='myenv',
            job_id='999',
        )

        self.backend.fetch(test_job.id)
        test_job.refresh_from_db()
        self.assertTrue(test_job.can_resubmit)

        # should not crash
        core_models.TestRun.objects.get(
            build__project=self.project,
            environment__slug='myenv',
            build__version='1',
            job_id='999',
            job_status='Incomplete',
            completed=False,
        )

    @patch('squad.ci.backend.null.Backend.job_url', return_value="http://example.com/123")
    @patch('squad.ci.backend.null.Backend.fetch')
    @patch('squad.ci.models.ReceiveTestRun.__call__')
    def test_fetch_sets_fetched_at(self, receive, backend_fetch, backend_job_url):
        backend_fetch.return_value = ('Completed', True, {}, {}, {}, None)

        env = self.project.environments.create(slug='foo')
        receive.return_value = (self.build.test_runs.create(environment=env), None)

        test_job = self.create_test_job(
            backend=self.backend,
            definition='foo: 1',
            environment='myenv',
            job_id='999',
        )
        self.backend.fetch(test_job.id)
        test_job.refresh_from_db()
        self.assertIsNotNone(test_job.fetched_at)

    @patch.object(models.Backend, '__postprocess_testjob__')
    @patch('squad.ci.backend.null.Backend.job_url', return_value="http://example.com/123")
    @patch('squad.ci.backend.null.Backend.fetch')
    @patch('squad.ci.models.ReceiveTestRun.__call__')
    def test_fetch_postprocessing(self, receive, backend_fetch, backend_job_url, postprocess):
        backend_fetch.return_value = ('Completed', True, {}, {}, {}, None)

        env = self.project.environments.create(slug='foo')
        receive.return_value = (self.build.test_runs.create(environment=env), None)

        test_job = self.create_test_job(
            backend=self.backend,
            definition='foo: 1',
            environment='myenv',
            job_id='999',
        )
        self.backend.fetch(test_job.id)
        postprocess.assert_called()


class BackendSubmitTest(BackendTestBase):

    @patch('squad.ci.models.Backend.get_implementation')
    def test_submit(self, get_implementation):
        test_job = self.create_test_job()
        impl = MagicMock()
        impl.submit = MagicMock(return_value=['999'])
        get_implementation.return_value = impl

        self.backend.submit(test_job)
        test_job.refresh_from_db()

        impl.submit.assert_called()
        self.assertTrue(test_job.submitted)
        self.assertIsNotNone(test_job.submitted_at)
        self.assertEqual('999', test_job.job_id)


class TestJobTest(TestCase):

    def setUp(self):
        self.group = core_models.Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.build = self.project.builds.create(version='1')
        self.backend = models.Backend.objects.create(
            url='http://example.com',
            username='foobar',
            token='mypassword',
        )

    def test_basics(self):
        testjob = models.TestJob.objects.create(
            target=self.project,
            target_build=self.build,
            environment='myenv',
            backend=self.backend,
        )
        self.assertIsNone(testjob.job_id)

    @patch('squad.ci.models.Backend.get_implementation')
    def test_cancel(self, get_implementation):
        test_job = models.TestJob.objects.create(
            target=self.project,
            target_build=self.build,
            environment='myenv',
            backend=self.backend,
            submitted=True,
            job_id=123
        )
        impl = MagicMock()
        impl.cancel = MagicMock(return_value=True)
        get_implementation.return_value = impl

        test_job.cancel()

        impl.cancel.assert_called()

    @patch('squad.ci.models.Backend.get_implementation')
    def test_cancel_not_submitted(self, get_implementation):
        test_job = models.TestJob.objects.create(
            target=self.project,
            target_build=self.build,
            environment='myenv',
            backend=self.backend,
            submitted=False
        )
        impl = MagicMock()
        impl.cancel = MagicMock(return_value=True)
        get_implementation.return_value = impl

        test_job.cancel()

        impl.cancel.assert_not_called()
        test_job.refresh_from_db()
        self.assertTrue(test_job.fetched)
        self.assertTrue(test_job.submitted)
        self.assertIsNotNone(test_job.failure)

    @patch('squad.ci.backend.null.Backend.resubmit', return_value="1")
    def test_records_resubmitted_count(self, backend_resubmit):
        testjob = models.TestJob.objects.create(
            target=self.project,
            target_build=self.build,
            environment='myenv',
            backend=self.backend,
            submitted=True,
            can_resubmit=True,
            job_id="12345",
        )
        testjob.resubmit()
        self.assertEqual(1, testjob.resubmitted_count)

    @patch('squad.ci.backend.null.Backend.resubmit', return_value="1")
    def test_delete_results_resubmitted_job(self, backend_resubmit):
        env, _ = self.project.environments.get_or_create(slug='myenv')
        testrun = self.build.test_runs.create(environment=env)
        suite, _ = self.project.suites.get_or_create(slug='mysuite')
        metadata = core_models.SuiteMetadata.objects.create(suite=suite.slug, name='mytest', kind='test')
        testrun.tests.create(metadata=metadata, suite=suite, result=True, environment=env, build=self.build)

        testjob = models.TestJob.objects.create(
            target=self.project,
            target_build=self.build,
            environment='myenv',
            backend=self.backend,
            testrun=testrun,
            submitted=True,
            can_resubmit=True,
            job_id="12345",
        )
        testjob.resubmit()
        self.assertEqual(1, testjob.resubmitted_count)

        # Check that the original testrun still exists
        testrun.refresh_from_db()
        self.assertEqual(1, self.build.tests.count())

        # Configure project to remove TestJob's results on resubmission
        self.project.project_settings = '{"CI_DELETE_RESULTS_RESUBMITTED_JOBS": true}'
        self.project.save()

        testjob.can_resubmit = True
        testjob.save()

        testjob.refresh_from_db()
        testjob.resubmit()
        testjob.refresh_from_db()

        self.assertEqual(2, testjob.resubmitted_count)

        # Check that the original testrun still exists
        with self.assertRaises(core_models.TestRun.DoesNotExist):
            testrun.refresh_from_db()

        self.assertEqual(0, self.build.tests.count())

    def mock_backend_fetch(test_job):
        status = 'Complete'
        completed = True
        metadata = {}
        tests = {'mysuite/mytest': 'pass'}
        metrics = {}
        logs = ''
        return status, completed, metadata, tests, metrics, logs

    @patch('requests.post')
    @patch('squad.ci.backend.null.Backend.fetch', side_effect=mock_backend_fetch)
    @patch('squad.ci.backend.null.Backend.resubmit', return_value="1")
    @patch('squad.ci.backend.null.Backend.submit', return_value=["1"])
    @patch('squad.ci.backend.null.Backend.job_url', return_value="http://job.url/")
    @patch('squad.core.tasks.notification.notify_patch_build_finished.delay')
    def test_resubmitted_job_retriggers_build_events(self, patch_notification, job_url, backend_submit, backend_resubmit, fetch, post):
        callback_url = 'http://callback.com/'
        self.build.callbacks.create(url=callback_url, event=core_models.Callback.events.ON_BUILD_FINISHED)
        testjob = self.build.test_jobs.create(
            target=self.project,
            environment='myenv',
            backend=self.backend,
            job_id='12345',
            submitted=True,
        )
        self.backend.fetch(testjob.id)

        self.build.refresh_from_db()
        testjob.refresh_from_db()

        # Ensures build is finished and events are triggered
        self.assertTrue(self.build.status.finished)
        self.assertTrue(self.build.status.notified)
        self.assertTrue(self.build.patch_notified)
        post.assert_called_with(callback_url)
        patch_notification.assert_called_with(self.build.id)
        self.assertEqual(1, self.build.tests.count())
        self.assertEqual(1, self.build.callbacks.filter(is_sent=True).count())

        # Reset mocks
        post.reset_mock()
        patch_notification.reset_mock()

        # Submit a new job, make sure build events are NOT reset by default
        submit_testjob = self.build.test_jobs.create(
            target=self.project,
            environment='myenv',
            backend=self.backend,
            job_status='Complete',
        )
        self.backend.submit(submit_testjob)
        self.assertTrue(self.build.status.finished)
        self.assertTrue(self.build.status.notified)
        self.assertTrue(self.build.patch_notified)
        self.assertEqual(1, self.build.callbacks.filter(is_sent=True).count())

        # Now fetch it, and make sure events DID NOT get triggered
        submit_testjob.job_id = "2"
        submit_testjob.save()
        self.backend.fetch(submit_testjob.id)
        post.assert_not_called()
        patch_notification.assert_not_called()

        # Repeat steps above, resubmit is used instead of submit
        resubmit_testjob = self.build.test_jobs.create(
            target=self.project,
            environment='myenv',
            backend=self.backend,
            job_status='Complete',
        )
        resubmit_testjob.resubmit()
        self.assertTrue(self.build.status.finished)
        self.assertTrue(self.build.status.notified)
        self.assertTrue(self.build.patch_notified)
        self.assertEqual(1, self.build.callbacks.filter(is_sent=True).count())

        # Now fetch it, and make sure events DID NOT get triggered
        resubmit_testjob.job_id = "3"
        resubmit_testjob.save()
        self.backend.fetch(resubmit_testjob.id)
        post.assert_not_called()
        patch_notification.assert_not_called()

        # Time for the truth! Configure project settings to allow build events
        # to get reset on submit/resubmit
        self.project.project_settings = '{"CI_RESET_BUILD_EVENTS_ON_JOB_RESUBMISSION": true}'
        self.project.__settings__ = None
        self.project.save()

        # Submit a new job, make sure build events ARE reset due to project setting
        submit_testjob = self.build.test_jobs.create(
            target=self.project,
            environment='myenv',
            backend=self.backend,
            job_status='Complete',
        )
        self.backend.submit(submit_testjob)
        self.assertFalse(self.build.status.finished)
        self.assertFalse(self.build.status.notified)
        self.assertFalse(self.build.patch_notified)
        self.assertEqual(0, self.build.callbacks.filter(is_sent=True).count())

        # Now fetch it, and make sure events GET triggered
        submit_testjob.job_id = "4"
        submit_testjob.save()
        self.backend.fetch(submit_testjob.id)
        self.build.refresh_from_db()
        self.build.status.refresh_from_db()
        submit_testjob.refresh_from_db()
        self.assertTrue(self.build.status.finished)
        self.assertTrue(self.build.status.notified)
        self.assertTrue(self.build.patch_notified)
        post.assert_called_with(callback_url)
        patch_notification.assert_called_with(self.build.id)
        self.assertEqual(4, self.build.tests.count())
        self.assertEqual(1, self.build.callbacks.filter(is_sent=True).count())

        # Reset mocks
        post.reset_mock()
        patch_notification.reset_mock()

        # Resubmit a new job, make sure build events ARE reset due to project setting
        resubmit_testjob = self.build.test_jobs.create(
            target=self.project,
            environment='myenv',
            backend=self.backend,
            job_status='Complete',
        )
        self.backend.submit(resubmit_testjob)
        self.assertFalse(self.build.status.finished)
        self.assertFalse(self.build.status.notified)
        self.assertFalse(self.build.patch_notified)
        self.assertEqual(0, self.build.callbacks.filter(is_sent=True).count())

        # Now fetch it, and make sure events GET triggered
        resubmit_testjob.job_id = "5"
        resubmit_testjob.save()
        self.backend.fetch(resubmit_testjob.id)
        self.build.refresh_from_db()
        self.build.status.refresh_from_db()
        resubmit_testjob.refresh_from_db()
        self.assertTrue(self.build.status.finished)
        self.assertTrue(self.build.status.notified)
        self.assertTrue(self.build.patch_notified)
        post.assert_called_with(callback_url)
        patch_notification.assert_called_with(self.build.id)
        self.assertEqual(5, self.build.tests.count())
        self.assertEqual(1, self.build.callbacks.filter(is_sent=True).count())

    @patch('squad.ci.backend.null.Backend.resubmit', side_effect=SubmissionIssue)
    def test_force_resubmit_exception(self, backend_resubmit):
        testjob = models.TestJob.objects.create(
            target=self.project,
            target_build=self.build,
            environment='myenv',
            backend=self.backend,
            submitted=True,
            can_resubmit=True,
            job_id="12345",
        )
        testjob.force_resubmit()
        self.assertEqual(0, testjob.resubmitted_jobs.count())
        self.assertEqual(0, testjob.resubmitted_count)
        self.assertEqual("12345", testjob.job_id)

    @patch('squad.ci.backend.null.Backend.submit', return_value=["12345"])
    def test_force_resubmit_unsubmitted_job(self, backend_resubmit):
        # By "unsubmitted", maybe a cancelled before submission or a submission that went wrong, and the
        # user just wants to force_resubmit it
        testjob = models.TestJob.objects.create(
            target=self.project,
            target_build=self.build,
            environment='myenv',
            backend=self.backend,
        )
        testjob.force_resubmit()
        self.assertEqual(0, testjob.resubmitted_jobs.count())
        self.assertEqual(0, testjob.resubmitted_count)
        self.assertEqual('12345', testjob.job_id)

    def test_show_definition_hides_secrets(self):
        definition = "foo: bar\nsecrets:\n  baz: qux\n"
        testjob = models.TestJob(
            definition=definition
        )
        display = yaml.safe_load(testjob.show_definition)
        self.assertNotEqual('qux', display['secrets']['baz'])

    def test_show_definition_non_dict(self):
        definition = "something that doesn't matter"
        testjob = models.TestJob(
            definition=definition
        )
        display = yaml.safe_load(testjob.show_definition)
        self.assertEqual(definition, display)
