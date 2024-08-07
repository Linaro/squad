from django.test import TestCase, TransactionTestCase, tag
from django.db import connection
from test.mock import patch
import time
import threading


from celery.exceptions import Retry


from squad.ci import models
from squad.core import models as core_models
from squad.core.tasks import ReceiveTestRun
from squad.ci.tasks import poll, fetch, submit
from squad.ci.utils import task_id
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
        fetch_method.apply_async.assert_called_with(args=(testjob.id,), task_id=task_id(testjob))


class FetchTest(TestCase):

    def setUp(self):
        group = core_models.Group.objects.create(slug='test')
        project = group.projects.create(slug='test')
        build = project.builds.create(version='test')
        backend = models.Backend.objects.create()
        self.test_job = models.TestJob.objects.create(
            backend=backend,
            target=project,
            target_build=build,
            job_id='test',
        )

    def mock_backend_fetch(test_job):
        status = ''
        completed = True
        metadata = {}
        tests = {}
        metrics = {}
        logs = ''
        test_job.failure = None
        test_job.save()
        return status, completed, metadata, tests, metrics, logs

    @patch('squad.ci.models.Backend.fetch')
    def test_fetch(self, fetch_method):
        fetch.apply(args=[self.test_job.id])
        fetch_method.assert_called_with(self.test_job.id)

    @patch('squad.ci.backend.null.Backend.fetch')
    def test_exception_when_fetching(self, fetch_method):
        fetch_method.side_effect = FetchIssue("ERROR")
        fetch.apply(args=[self.test_job.id])

        self.test_job.refresh_from_db()
        self.assertEqual("ERROR", self.test_job.failure)
        self.assertTrue(self.test_job.fetched)

    @patch('squad.ci.backend.null.Backend.fetch')
    def test_temporary_exception_when_fetching(self, fetch_method):
        fetch_method.side_effect = TemporaryFetchIssue("ERROR")
        fetch.apply(args=[self.test_job.id])

        self.test_job.refresh_from_db()
        self.assertEqual("ERROR", self.test_job.failure)
        self.assertFalse(self.test_job.fetched)

    @patch('squad.ci.backend.null.Backend.fetch')
    @patch('squad.ci.backend.null.Backend.job_url')
    def test_clear_exception_after_successful_fetch(self, job_url, fetch_method):
        fetch_method.side_effect = TemporaryFetchIssue("ERROR")
        fetch.apply(args=[self.test_job.id])

        self.test_job.refresh_from_db()
        self.assertEqual("ERROR", self.test_job.failure)
        self.assertFalse(self.test_job.fetched)

        fetch_method.side_effect = FetchTest.mock_backend_fetch
        job_url.side_effect = lambda a: 'test'
        fetch.apply(args=[self.test_job.id])
        self.test_job.refresh_from_db()
        fetch_method.assert_called_with(self.test_job)
        self.assertIsNone(self.test_job.failure)
        self.assertTrue(self.test_job.fetched)

    @patch('squad.ci.backend.null.Backend.fetch')
    def test_counts_attempts_with_temporary_exceptions(self, fetch_method):
        attemps = self.test_job.fetch_attempts
        fetch_method.side_effect = TemporaryFetchIssue("ERROR")
        fetch.apply(args=[self.test_job.id])

        self.test_job.refresh_from_db()
        self.assertEqual(attemps + 1, self.test_job.fetch_attempts)

    @patch('squad.ci.models.Backend.fetch')
    def test_fetch_no_job_id(self, fetch_method):
        testjob = models.TestJob.objects.create(
            backend=self.test_job.backend,
            target=self.test_job.target,
            target_build=self.test_job.target_build,
        )
        fetch.apply(args=[testjob.id])
        fetch_method.assert_not_called()

    @patch('squad.ci.models.Backend.fetch')
    def test_fetch_deleted_job(self, fetch_method):
        fetch.apply(args=[99999999999])
        fetch_method.assert_not_called()


class FetchTestRaceCondition(TransactionTestCase):

    def setUp(self):
        group = core_models.Group.objects.create(slug='test')
        project = group.projects.create(slug='test')
        build = project.builds.create(version='test-build')
        backend = models.Backend.objects.create()
        self.testjob = models.TestJob.objects.create(
            backend=backend,
            target=project,
            target_build=build,
            job_id='test',
        )

    def mock_backend_fetch(test_job):
        time.sleep(0.5)
        status = ''
        completed = True
        metadata = {}
        tests = {}
        metrics = {}
        logs = ''
        return status, completed, metadata, tests, metrics, logs

    @tag('skip_sqlite')
    @patch('squad.ci.backend.null.Backend.job_url', return_value='http://url')
    @patch('squad.ci.backend.null.Backend.fetch', side_effect=mock_backend_fetch)
    def test_race_condition_on_fetch(self, fetch_method, job_url_method):

        def thread(testjob_id):
            fetch(testjob_id)
            connection.close()

        parallel_task_1 = threading.Thread(target=thread, args=(self.testjob.id,))
        parallel_task_2 = threading.Thread(target=thread, args=(self.testjob.id,))

        parallel_task_1.start()
        parallel_task_2.start()

        parallel_task_1.join()
        parallel_task_2.join()
        self.assertEqual(1, fetch_method.call_count)


__sleeping__ = False


class FetchTestRaceConditionWaitAllJobsToBeFetched(TransactionTestCase):
    """
    If another testjob for this build is finished, it'll trigger UpdateProjectStatus
    which will invoke Build.finished and will see that all testjobs for this build
    are finished. Except that if this current test job is still running plugins, like
    VTS/CTS which take long time, the build will be considered to be finished
    and finishing events will be triggered such as email reports and callbacks
    """

    def setUp(self):
        group = core_models.Group.objects.create(slug='test')
        project = group.projects.create(slug='test')
        self.build = project.builds.create(version='test-build')
        backend = models.Backend.objects.create()
        self.testjob1 = models.TestJob.objects.create(
            backend=backend,
            target=project,
            target_build=self.build,
            job_id='job-1',
        )
        self.testjob2 = models.TestJob.objects.create(
            backend=backend,
            target=project,
            target_build=self.build,
            job_id='job-2',
        )

    def mock_backend_fetch(test_job):
        status = ''
        completed = True
        metadata = {}
        tests = {}
        metrics = {}
        logs = ''
        return status, completed, metadata, tests, metrics, logs

    def mock_receive_testrun(target, update_project_status):
        global __sleeping__
        # Let's present job1 takes a bit longer
        if __sleeping__ is False:
            time.sleep(2)
            __sleeping__ = True
        return ReceiveTestRun(target, update_project_status=update_project_status)

    @tag('skip_sqlite')
    @patch('squad.ci.backend.null.Backend.job_url')
    @patch('squad.ci.models.ReceiveTestRun', side_effect=mock_receive_testrun)
    @patch('squad.ci.backend.null.Backend.fetch', side_effect=mock_backend_fetch)
    def test_race_condition_on_fetch(self, fetch_method, mock_receive, mock_url):
        mock_url.return_value = "job-url"

        def thread(testjob_id):
            fetch(testjob_id)
            connection.close()

        parallel_task_1 = threading.Thread(target=thread, args=(self.testjob1.id,))
        parallel_task_2 = threading.Thread(target=thread, args=(self.testjob2.id,))

        parallel_task_1.start()
        parallel_task_2.start()

        time.sleep(1)

        self.testjob1.refresh_from_db()
        self.testjob2.refresh_from_db()

        finished, _ = self.build.finished
        self.assertFalse(finished)

        parallel_task_1.join()
        parallel_task_2.join()

        finished, _ = self.build.finished
        self.assertTrue(finished)


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

    @patch('squad.ci.models.Backend.submit')
    def test_avoid_multiple_submissions(self, submit_method):
        self.test_job.submitted = True
        self.test_job.save()
        submit.apply(args=[self.test_job.id])
        self.assertFalse(submit_method.called)

    @patch('squad.ci.tasks.submit.retry')
    @patch('squad.ci.models.Backend.submit')
    def test_submit_overwrite_failure_after_success(self, submit_method, retry):
        exception = TemporarySubmissionIssue("TEMPORARY ERROR")
        retry.return_value = Retry()
        submit_method.side_effect = exception

        with self.assertRaises(Retry):
            submit.apply(args=[self.test_job.id])

        retry.assert_called_with(exc=exception, countdown=3600)
        self.test_job.refresh_from_db()
        self.assertEqual(self.test_job.failure, "TEMPORARY ERROR")

        submit_method.side_effect = None
        submit.apply(args=[self.test_job.id])
        self.test_job.refresh_from_db()
        self.assertIsNone(self.test_job.failure)
