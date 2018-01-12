from squad.core import models as core_models
from squad.ci import models
from django.test import TestCase
from django.test import Client
from mock import patch


class TestJobViewTest(TestCase):

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
