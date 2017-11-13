from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.test import Client
from mock import patch, MagicMock


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

    def create_test_job(self, **attrs):
        return self.backend.test_jobs.create(target=self.project, **attrs)


class BackendPollTest(BackendTestBase):

    def test_poll(self):
        test_job = self.create_test_job(submitted=True)
        jobs = list(self.backend.poll())
        self.assertEqual([test_job], jobs)

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

    @patch("squad.ci.models.Backend.really_fetch")
    def test_fetch_skips_already_fetched(self, really_fetch):
        test_job = self.create_test_job(submitted=True, fetched=True)
        self.backend.fetch(test_job)

        really_fetch.assert_not_called()

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_really_fetch(self, get_implementation, __now__):
        impl = MagicMock()
        impl.fetch = MagicMock(return_value=None)
        get_implementation.return_value = impl

        test_job = self.create_test_job()
        self.backend.really_fetch(test_job)

        test_job.refresh_from_db()
        self.assertEqual(NOW, test_job.last_fetch_attempt)
        self.assertFalse(test_job.fetched)

        get_implementation.assert_called()
        impl.fetch.assert_called()

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_really_fetch_creates_testrun(self, get_implementation, __now__):
        metadata = {"foo": "bar"}
        tests = {"foo": "pass"}
        metrics = {"bar": 1}
        results = ('Complete', True, metadata, tests, metrics, "abc")

        impl = MagicMock()
        impl.fetch = MagicMock(return_value=results)
        impl.job_url = MagicMock(return_value="http://www.example.com")
        get_implementation.return_value = impl

        test_job = self.create_test_job(
            backend=self.backend,
            definition='foo: 1',
            build='1',
            environment='myenv',
            job_id='999',
        )

        self.backend.really_fetch(test_job)

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
                name="foo",
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
        self.assertTrue(test_job.fetched)

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_really_fetch_with_empty_results(self, get_implementation, __now__):
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
            build='1',
            environment='myenv',
            job_id='999',
        )

        self.backend.really_fetch(test_job)

        # should not crash
        test_run = core_models.TestRun.objects.get(
            build__project=self.project,
            environment__slug='myenv',
            build__version='1',
            job_id='999',
            job_status='Complete',
        )
        self.assertTrue(test_job.can_resubmit)
        self.assertFalse(test_run.completed)

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_really_fetch_with_only_results(self, get_implementation, __now__):
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
            build='1',
            environment='myenv',
            job_id='999',
        )

        self.backend.really_fetch(test_job)

        # should not crash
        test_run = core_models.TestRun.objects.get(
            build__project=self.project,
            environment__slug='myenv',
            build__version='1',
            job_id='999',
            job_status='Complete',
        )
        self.assertFalse(test_job.can_resubmit)
        self.assertTrue(test_run.completed)

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_really_fetch_with_only_metrics(self, get_implementation, __now__):
        metadata = {"foo": "bar"}
        tests = {}
        metrics = {"foo": 10}
        results = ('Complete', True, metadata, tests, metrics, "abc")

        impl = MagicMock()
        impl.fetch = MagicMock(return_value=results)
        impl.job_url = MagicMock(return_value="http://www.example.com")
        get_implementation.return_value = impl

        test_job = self.create_test_job(
            backend=self.backend,
            definition='foo: 1',
            build='1',
            environment='myenv',
            job_id='999',
        )

        self.backend.really_fetch(test_job)

        # should not crash
        test_run = core_models.TestRun.objects.get(
            build__project=self.project,
            environment__slug='myenv',
            build__version='1',
            job_id='999',
            job_status='Complete',
        )
        self.assertFalse(test_job.can_resubmit)
        self.assertTrue(test_run.completed)

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_create_testrun_job_url(self, get_implementation, __now__):
        metadata = {"foo": "bar"}
        tests = {"foo": "pass"}
        metrics = {"bar": 1}
        results = ('Complete', True, metadata, tests, metrics, "abc")
        test_job_url = "http://www.example.com"

        impl = MagicMock()
        impl.fetch = MagicMock(return_value=results)
        impl.job_url = MagicMock(return_value=test_job_url)
        get_implementation.return_value = impl

        test_job = self.create_test_job(
            backend=self.backend,
            definition='foo: 1',
            build='1',
            environment='myenv',
            job_id='999',
        )

        self.backend.really_fetch(test_job)

        # should not crash
        test_run = core_models.TestRun.objects.get(
            build__project=self.project,
            environment__slug='myenv',
            build__version='1',
            job_id='999',
            job_status='Complete',
            completed=True,
        )
        self.assertEqual(test_run.job_url, test_job_url)

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_really_fetch_sets_testjob_can_resubmit_and_testrun_completed(self, get_implementation, __now__):
        metadata = {"foo": "bar"}
        tests = {"foo": "pass"}
        metrics = {"bar": 1}
        results = ('Incomplete', False, metadata, tests, metrics, "abc")
        #                        ^^^^^ job resulted in an infra failure

        impl = MagicMock()
        impl.fetch = MagicMock(return_value=results)
        impl.job_url = MagicMock(return_value="http://www.example.com")
        get_implementation.return_value = impl

        test_job = self.create_test_job(
            backend=self.backend,
            definition='foo: 1',
            build='1',
            environment='myenv',
            job_id='999',
        )

        self.backend.really_fetch(test_job)
        self.assertTrue(test_job.can_resubmit)

        # should not crash
        core_models.TestRun.objects.get(
            build__project=self.project,
            environment__slug='myenv',
            build__version='1',
            job_id='999',
            job_status='Incomplete',
            completed=True,  # results are not empty -> completed = True
        )

    @patch('django.utils.timezone.now', return_value=NOW)
    @patch('squad.ci.models.Backend.get_implementation')
    def test_really_fetch_sets_testjob_can_resubmit_and_testrun_completed2(self, get_implementation, __now__):
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
            build='1',
            environment='myenv',
            job_id='999',
        )

        self.backend.really_fetch(test_job)
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


class BackendSubmitTest(BackendTestBase):

    @patch('squad.ci.models.Backend.get_implementation')
    def test_submit(self, get_implementation):
        test_job = self.create_test_job()
        impl = MagicMock()
        impl.submit = MagicMock(return_value='999')
        get_implementation.return_value = impl

        self.backend.submit(test_job)
        test_job.refresh_from_db()

        impl.submit.assert_called()
        self.assertTrue(test_job.submitted)
        self.assertEqual('999', test_job.job_id)


class TestJobTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_basics(self):
        group = core_models.Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
        backend = models.Backend.objects.create(
            url='http://example.com',
            username='foobar',
            token='mypassword',
        )
        testjob = models.TestJob.objects.create(
            target=project,
            build='1',
            environment='myenv',
            backend=backend,
        )
        self.assertIsNone(testjob.job_id)

    def test_testjob_page(self):
        group = core_models.Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
        backend = models.Backend.objects.create(
            url='http://example.com',
            username='foobar',
            token='mypassword',
        )
        job_id = 1234
        testjob = models.TestJob.objects.create(
            target=project,
            build='1',
            environment='myenv',
            backend=backend,
            job_id=job_id
        )

        response = self.client.get('/testjob/%s' % testjob.id)
        self.assertEqual(200, response.status_code)

    @patch("squad.ci.models.Backend.get_implementation")
    def test_testjob_redirect(self, implementation):
        return_url = "http://example.com/job/1234"

        class BackendImpl:
            def job_url(self, job_id):
                return return_url

        group = core_models.Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
        backend = models.Backend.objects.create(
            url='http://example.com',
            username='foobar',
            token='mypassword',
        )
        implementation.return_value = BackendImpl()
        testjob = models.TestJob.objects.create(
            target=project,
            build='1',
            environment='myenv',
            backend=backend,
            job_id=1234
        )

        response = self.client.get('/testjob/%s' % testjob.id)
        backend.get_implementation.assert_called()
        self.assertEqual(302, response.status_code)
        self.assertEqual(return_url, response.url)

    def test_testjob_non_existing(self):
        response = self.client.get('/testjob/9999')
        self.assertEqual(404, response.status_code)
