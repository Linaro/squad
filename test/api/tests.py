import os


from django.test import TestCase
from django.test import Client
from django.test.utils import setup_test_environment


from squad.core import models


tests_file = os.path.join(os.path.dirname(__file__), 'tests.csv')
benchmarks_file = os.path.join(os.path.dirname(__file__), 'benchmarks.csv')
log_file = os.path.join(os.path.dirname(__file__), 'test_run.log')


class APIClient(Client):

    def __init__(self, token):
        self.token = token
        return super(APIClient, self).__init__(token)

    def post(self, *args, **kwargs):
        if not kwargs.get('HTTP_AUTH_TOKEN'):
            kwargs = kwargs.copy()
            kwargs.update({'HTTP_AUTH_TOKEN': self.token})
        return super(APIClient, self).post(*args, **kwargs)


class ApiTest(TestCase):

    def setUp(self):
        setup_test_environment()

        self.group = models.Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.project.tokens.create(key='thekey')

        self.client = APIClient('thekey')

    def test_create_object_hierarchy(self):
        response = self.client.post('/api/mygroup/myproject/1.0.0/myenvironment')
        self.assertEqual(response.status_code, 201)

        self.project.builds.get(version='1.0.0')
        self.project.environments.get(slug='myenvironment')

    def test_create_test_run(self):
        test_runs = models.TestRun.objects.count()
        self.client.post('/api/mygroup/myproject/1.0.0/myenvironment')
        self.assertEqual(test_runs + 1, models.TestRun.objects.count())

    def test_receives_tests_file(self):
        with open(tests_file) as f:
            self.client.post(
                '/api/mygroup/myproject/1.0.0/myenvironment',
                {'tests': f}
            )
        self.assertTrue(models.TestRun.objects.last().tests_file is not None)

    def test_receives_benchmarks_file(self):
        with open(benchmarks_file) as f:
            self.client.post(
                '/api/mygroup/myproject/1.0.0/myenvironment',
                {'benchmarks': f}
            )
        self.assertTrue(models.TestRun.objects.last().benchmarks_file is not None)

    def test_receives_log_file(self):
        with open(log_file) as f:
            self.client.post('/api/mygroup/myproject/1.0.0/myenvironment',
                             {'log': f})
        self.assertTrue(models.TestRun.objects.last().log_file is not None)

    def test_unauthorized(self):
        client = Client()  # regular client without auth support
        response = client.post('/api/mygroup/myproject/1.0.0/myenvironment')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(models.TestRun.objects.count(), 0)

    def test_forbidden(self):
        self.client.token = 'wrongtoken'
        response = self.client.post('/api/mygroup/myproject/1.0.0/myenv')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(models.TestRun.objects.count(), 0)
