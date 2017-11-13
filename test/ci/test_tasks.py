from django.test import TestCase
from mock import patch


from celery.exceptions import Retry


from squad.ci import models
from squad.core import models as core_models
from squad.ci.tasks import poll, fetch, submit
from squad.ci.exceptions import SubmissionIssue, TemporarySubmissionIssue
from squad.ci.exceptions import FetchIssue, TemporaryFetchIssue


class PollTest(TestCase):

    @patch("squad.ci.models.Backend.poll")
    def test_poll_no_backends(self, poll_method):
        poll.apply()
        poll_method.assert_not_called()

    @patch("squad.ci.models.Backend.poll")
    def test_poll_all_backends(self, poll_method):
        models.Backend.objects.create()
        poll.apply()
        poll_method.assert_called_once()

    @patch("squad.ci.models.Backend.poll")
    def test_poll_one_backend(self, poll_method):
        b1 = models.Backend.objects.create(name='b1')
        models.Backend.objects.create(name='b2')
        poll.apply(args=[b1.id])
        poll_method.assert_called_once()

    @patch("squad.ci.tasks.fetch")
    def test_poll_calls_fetch_on_all_test_jobs(self, fetch_method):
        group = core_models.Group.objects.create(slug='testgroup')
        project = group.projects.create(slug='testproject')
        backend = models.Backend.objects.create(name='b1')
        testjob = backend.test_jobs.create(target=project, submitted=True)
        poll.apply()
        fetch_method.delay.assert_called_with(testjob.id)


class FetchTest(TestCase):

    def setUp(self):
        group = core_models.Group.objects.create(slug='test')
        project = group.projects.create(slug='test')
        backend = models.Backend.objects.create()
        self.test_job = models.TestJob.objects.create(
            backend=backend,
            target=project,
        )

    @patch('squad.ci.models.Backend.fetch')
    def test_fetch(self, fetch_method):
        fetch.apply(args=[self.test_job.id])
        fetch_method.assert_called_with(self.test_job)

    @patch('squad.ci.models.Backend.really_fetch')
    def test_really_fetch(self, really_fetch_method):
        fetch.apply(args=[self.test_job.id])
        really_fetch_method.assert_called_with(self.test_job)

    @patch('squad.ci.models.Backend.fetch')
    def test_exception_when_fetching(self, fetch_method):
        fetch_method.side_effect = FetchIssue("ERROR")
        fetch.apply(args=[self.test_job.id])

        self.test_job.refresh_from_db()
        self.assertEqual("ERROR", self.test_job.failure)
        self.assertTrue(self.test_job.fetched)

    @patch('squad.ci.models.Backend.fetch')
    def test_temporary_exception_when_fetching(self, fetch_method):
        fetch_method.side_effect = TemporaryFetchIssue("ERROR")
        fetch.apply(args=[self.test_job.id])

        self.test_job.refresh_from_db()
        self.assertEqual("ERROR", self.test_job.failure)
        self.assertFalse(self.test_job.fetched)

    @patch('squad.ci.models.Backend.fetch')
    def test_counts_attempts_with_temporary_exceptions(self, fetch_method):
        attemps = self.test_job.fetch_attempts
        fetch_method.side_effect = TemporaryFetchIssue("ERROR")
        fetch.apply(args=[self.test_job.id])

        self.test_job.refresh_from_db()
        self.assertEqual(attemps + 1, self.test_job.fetch_attempts)


class SubmitTest(TestCase):

    def setUp(self):
        group = core_models.Group.objects.create(slug='test')
        project = group.projects.create(slug='test')
        backend = models.Backend.objects.create()
        self.test_job = models.TestJob.objects.create(backend=backend, target=project)

    @patch('squad.ci.models.Backend.submit')
    def test_submit(self, submit_method):
        submit.apply(args=[self.test_job.id])
        submit_method.assert_called_with(self.test_job)

    @patch('squad.ci.models.Backend.submit')
    def test_submit_fatal_error(self, submit_method):
        submit_method.side_effect = SubmissionIssue("ERROR")

        submit.apply(args=[self.test_job.id])

        self.test_job.refresh_from_db()
        self.assertEqual(self.test_job.failure, "ERROR")

    @patch('squad.ci.tasks.submit.retry')
    @patch('squad.ci.models.Backend.submit')
    def test_submit_temporary_error(self, submit_method, retry):
        exception = TemporarySubmissionIssue("TEMPORARY ERROR")
        retry.return_value = Retry()
        submit_method.side_effect = exception

        with self.assertRaises(Retry):
            submit.apply(args=[self.test_job.id])

        retry.assert_called_with(exc=exception, countdown=3600)
        self.test_job.refresh_from_db()
        self.assertEqual(self.test_job.failure, "TEMPORARY ERROR")
