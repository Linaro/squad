from squad.core import models as core_models
from squad.ci import models
from django.test import TestCase
from django.test import Client
from test.mock import patch


class TestJobViewTest(TestCase):

    def setUp(self):
        self.client = Client()
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

    @patch('squad.ci.backend.null.Backend.job_url', return_value=None)
    def test_testjob_page(self, backend_job_url):
        job_id = 1234
        testjob = models.TestJob.objects.create(
            target=self.project,
            target_build=self.build,
            environment='myenv',
            backend=self.backend,
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

        implementation.return_value = BackendImpl()
        testjob = models.TestJob.objects.create(
            target=self.project,
            target_build=self.build,
            environment='myenv',
            backend=self.backend,
            job_id=1234
        )

        response = self.client.get('/testjob/%s' % testjob.id)
        self.backend.get_implementation.assert_called()
        self.assertEqual(302, response.status_code)
        self.assertEqual(return_url, response.url)

    def test_testjob_non_existing(self):
        response = self.client.get('/testjob/9999')
        self.assertEqual(404, response.status_code)

    def test_testjob_non_integer(self):
        response = self.client.get('/testjob/9999%20abcd')
        self.assertEqual(404, response.status_code)
