from django.test import TestCase
from mock import patch

from squad.ci import models
from squad.core import models as core_models
from squad.ci.tasks import poll, fetch, submit


class PollTest(TestCase):

    @patch("squad.ci.models.Backend.poll")
    def test_poll_no_backends(self, poll_method):
        poll.apply()
        poll_method.assert_not_called()

    @patch("squad.ci.models.Backend.poll")
    def test_poll_one_backend(self, poll_method):
        models.Backend.objects.create()
        poll.apply()
        poll_method.assert_called_once()


class FetchTest(TestCase):

    @patch('squad.ci.models.Backend.really_fetch')
    def test_fetch(self, really_fetch):
        group = core_models.Group.objects.create(slug='test')
        project = group.projects.create(slug='test')

        backend = models.Backend.objects.create()
        test_job = models.TestJob.objects.create(backend=backend, target=project)

        fetch.apply(args=[test_job.id])
        really_fetch.assert_called_with(test_job)


class SubmitTest(TestCase):

    @patch('squad.ci.models.Backend.submit')
    def test_submit(self, submit_method):
        group = core_models.Group.objects.create(slug='test')
        project = group.projects.create(slug='test')

        backend = models.Backend.objects.create()
        test_job = models.TestJob.objects.create(backend=backend, target=project)

        submit.apply(args=[test_job.id])
        submit_method.assert_called_with(test_job)
