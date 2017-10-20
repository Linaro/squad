from django.test import TestCase
from django.test import Client
from django.contrib.auth.models import User


from squad.core import models
from squad.core.tasks import ReceiveTestRun


class FrontendTest(TestCase):

    def setUp(self):
        self.group = models.Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.user = User.objects.create(username='theuser')

        self.client = Client()
        self.client.force_login(self.user)

        ReceiveTestRun(self.project)(
            version='1.0',
            environment_slug='myenv',
            log_file='log file contents ...',
            tests_file='{}',
            metrics_file='{}',
            metadata_file='{ "job_id" : "1" }',
        )
        self.test_run = models.TestRun.objects.last()

    def hit(self, url, expected_status=200):
        response = self.client.get(url)
        self.assertEqual(expected_status, response.status_code)
        return response

    def test_home(self):
        self.hit('/')

    def test_group(self):
        self.hit('/mygroup/')

    def test_group_404(self):
        self.hit('/unexistinggroup/', 404)

    def test_project(self):
        self.hit('/mygroup/myproject/')

    def test_project_404(self):
        self.hit('/mygroup/unexistingproject/', 404)

    def test_project_no_build(self):
        self.project.builds.all().delete()
        self.hit('/mygroup/myproject/')

    def test_builds(self):
        self.hit('/mygroup/myproject/builds/')

    def test_build_404(self):
        self.hit('/mygroup/myproject/build/999/', 404)

    def test_test_run_build_404(self):
        self.hit('/mygroup/myproject/build/2.0.missing/testrun/999/', 404)

    def test_test_run_404(self):
        self.hit('/mygroup/myproject/build/1.0/testrun/999/', 404)

    def test_attachment(self):
        data = bytes('text file', 'utf-8')
        self.test_run.attachments.create(filename='foo.txt', data=data, length=len(data))
        response = self.hit('/mygroup/myproject/build/1.0/testrun/1/attachments/foo.txt')
        self.assertEqual('text/plain', response['Content-Type'])

    def test_log(self):
        response = self.hit('/mygroup/myproject/build/1.0/testrun/1/log')
        self.assertEqual('text/plain', response['Content-Type'])

    def test_no_log(self):
        self.test_run.log_file = None
        self.test_run.save()

        response = self.client.get('/mygroup/myproject/build/1.0/testrun/1/log')
        self.assertEqual(404, response.status_code)

    def test_tests(self):
        response = self.hit('/mygroup/myproject/build/1.0/testrun/1/tests')
        self.assertEqual('application/json', response['Content-Type'])

    def test_metrics(self):
        response = self.hit('/mygroup/myproject/build/1.0/testrun/1/metrics')
        self.assertEqual('application/json', response['Content-Type'])

    def test_metadata(self):
        response = self.hit('/mygroup/myproject/build/1.0/testrun/1/metadata')
        self.assertEqual('application/json', response['Content-Type'])
