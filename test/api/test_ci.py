import os
from django.test import TestCase, Client
from django.test.utils import override_settings
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from test.api import APIClient
from mock import patch, MagicMock


from squad.core import models as core_models
from squad.ci import models


job_definition_file = os.path.join(os.path.dirname(__file__), 'definition.yaml')


class CiApiTest(TestCase):

    def setUp(self):
        self.group = core_models.Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')

        self.project_submission_user = User.objects.create(username='project-user')
        usergroup = self.group.user_groups.create()
        self.project_submission_user.groups.add(usergroup)
        self.build = self.project.builds.create(version='1')
        Token.objects.create(user=self.project_submission_user, key='thekey')

        self.backend = models.Backend.objects.create(name='lava')
        self.client = APIClient('thekey')

    def test_auth(self):
        args = {
            'backend': 'lava',
            'definition': 'foo: 1',
        }
        self.client.token = 'invalid-token'
        r = self.client.post('/api/submitjob/mygroup/myproject/1/myenv', args)
        self.assertEqual(401, r.status_code)

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
                target_build=self.build,
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
    def test_auth_on_watch_testjob(self, fetch):
        testjob_id = 1234
        args = {
            'backend': 'lava',
            'testjob_id': testjob_id,
        }
        self.client.token = 'invalid-token'
        r = self.client.post('/api/watchjob/mygroup/myproject/1/myenv', args)
        self.assertEqual(401, r.status_code)

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
                target_build=self.build,
                backend=self.backend,
                submitted=True,
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

    @patch('squad.ci.models.Backend.get_implementation')
    def test_resubmit(self, get_implementation):
        impl = MagicMock()
        impl.resubmit = MagicMock()
        get_implementation.return_value = impl

        t = self.backend.test_jobs.create(
            target=self.project,
            can_resubmit=True
        )
        staff_user_password = "secret"
        staff_user = User.objects.create_superuser(
            username="staffuser",
            email="staff@example.com",
            password=staff_user_password,
            is_staff=True)
        staff_user.save()
        client = Client()
        client.login(username=staff_user.username, password=staff_user_password)
        r = client.get('/api/resubmit/%s' % t.pk)
        self.assertEqual(201, r.status_code)
        impl.resubmit.assert_called()
        t.refresh_from_db()
        self.assertEqual(False, t.can_resubmit)

    def test_disallowed_resubmit(self):
        t = self.backend.test_jobs.create(
            target=self.project,
            can_resubmit=True
        )
        r = self.client.get('/api/resubmit/%s' % t.pk)
        self.assertEqual(401, r.status_code)

    def test_resubmit_invalid_id(self):
        staff_user_password = "secret"
        staff_user = User.objects.create_superuser(
            username="staffuser",
            email="staff@example.com",
            password=staff_user_password,
            is_staff=True)
        staff_user.save()
        client = Client()
        client.login(username=staff_user.username, password=staff_user_password)

        r = client.get('/api/resubmit/999')
        self.assertEqual(400, r.status_code)
