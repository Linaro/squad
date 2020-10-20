from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.test import TestCase
from test.mock import patch, MagicMock
import yaml


from squad.core import models as core_models


from squad.ci import models
from squad.ci.backend.null import Backend


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
                name="bar",
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
        )
        testjob.resubmit()
        self.assertEqual(1, testjob.resubmitted_count)

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
