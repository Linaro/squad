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
            metadata='{ "job_id" : "1" }',
        )
        self.test_run = models.TestRun.objects.last()

    def hit(self, url):
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        return response

    def test_home(self):
        self.hit('/')

    def test_group(self):
        self.hit('/mygroup/')

    def test_project(self):
        self.hit('/mygroup/myproject/')

    def test_builds(self):
        self.hit('/mygroup/myproject/builds/')

    def test_attachment(self):
        data = bytes('text file', 'utf-8')
        self.test_run.attachments.create(filename='foo.txt', data=data, length=len(data))
        response = self.hit('/mygroup/myproject/build/1.0/testrun/1/attachments/foo.txt')
        self.assertEqual('text/plain', response['Content-Type'])

    def test_log(self):
        response = self.hit('/mygroup/myproject/build/1.0/testrun/1/log')
        self.assertEqual('text/plain', response['Content-Type'])

    def test_tests(self):
        response = self.hit('/mygroup/myproject/build/1.0/testrun/1/tests')
        self.assertEqual('application/json', response['Content-Type'])

    def test_metrics(self):
        response = self.hit('/mygroup/myproject/build/1.0/testrun/1/metrics')
        self.assertEqual('application/json', response['Content-Type'])

    def test_metadata(self):
        response = self.hit('/mygroup/myproject/build/1.0/testrun/1/metadata')
        self.assertEqual('application/json', response['Content-Type'])
