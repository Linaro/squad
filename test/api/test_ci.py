import os
from django.test import TestCase
from test.api import APIClient
from mock import patch


from squad.core import models as core_models
from squad.ci import models


job_definition_file = os.path.join(os.path.dirname(__file__), 'definition.yaml')


class CiApiTest(TestCase):

    def setUp(self):
        self.group = core_models.Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.project.tokens.create(key='thekey')
        self.backend = models.Backend.objects.create(name='lava')
        self.client = APIClient('thekey')

    def test_creates_test_run(self):
        args = {
            'backend': 'lava',
            'definition': 'foo: 1',
        }
        r = self.client.post('/api/submitjob/mygroup/myproject/1/myenv', args)
        self.assertEqual(201, r.status_code)
        self.assertEqual(
            1,
            models.TestJob.objects.filter(
                target=self.project,
                environment='myenv',
                build='1',
                backend=self.backend,
                definition='foo: 1',
            ).count()
        )

    def test_invalid_backend_test_run(self):
        args = {
            'backend': 'lava.foo',
            'definition': 'foo: 1',
        }
        r = self.client.post('/api/submitjob/mygroup/myproject/1/myenv', args)
        self.assertEqual(400, r.status_code)

    def test_missing_definition_test_run(self):
        args = {
            'backend': 'lava'
        }
        r = self.client.post('/api/submitjob/mygroup/myproject/1/myenv', args)
        self.assertEqual(400, r.status_code)

    def test_accepts_definition_as_file_upload(self):
        args = {
            'backend': 'lava',
            'definition': open(job_definition_file)
        }
        self.client.post('/api/submitjob/mygroup/myproject/1/myenv', args)

    @patch("squad.ci.tasks.submit.delay")
    def test_schedules_submission(self, submit):
        args = {
            'backend': 'lava',
            'definition': 'foo: 1',
        }
        self.client.post('/api/submitjob/mygroup/myproject/1/myenv', args)
        job_id = models.TestJob.objects.last().id
        submit.assert_called_with(job_id)

    @patch("squad.ci.tasks.fetch.delay")
    def test_watch_testjob(self, fetch):
        testjob_id = 1234
        args = {
            'backend': 'lava',
            'testjob_id': testjob_id,
        }
        r = self.client.post('/api/watchjob/mygroup/myproject/1/myenv', args)
        self.assertEqual(201, r.status_code)
        self.assertEqual(
            1,
            models.TestJob.objects.filter(
                target=self.project,
                environment='myenv',
                build='1',
                backend=self.backend,
                job_id=testjob_id
            ).count()
        )

    @patch("squad.ci.tasks.fetch.delay")
    def test_watch_testjob_mising_id(self, fetch):
        args = {
            'backend': 'lava'
        }
        r = self.client.post('/api/watchjob/mygroup/myproject/1/myenv', args)
        self.assertEqual(400, r.status_code)
