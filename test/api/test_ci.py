import os
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.admin.models import LogEntry, ADDITION
from rest_framework.authtoken.models import Token
from test.api import APIClient, RestAPIClient
from test.mock import patch, MagicMock


from squad.core import models as core_models
from squad.ci.exceptions import SubmissionIssue
from squad.ci import models


job_definition_file = os.path.join(os.path.dirname(__file__), 'definition.yaml')
twoline_job_definition_file = os.path.join(os.path.dirname(__file__), 'twoline_definition.yaml')


class CiApiTest(TestCase):

    def setUp(self):
        self.group = core_models.Group.objects.create(slug='mygroup')
        self.usergroup = core_models.UserNamespace.objects.create(slug='~project-member-user')
        self.project = self.group.projects.create(slug='myproject')
        self.userproject = self.usergroup.projects.create(slug='userproject')

        self.project_admin_user = User.objects.create(username='project-admin')
        self.group.add_admin(self.project_admin_user)
        self.project_privileged_user = User.objects.create(username='project-user')
        self.group.add_user(self.project_privileged_user, 'privileged')
        self.project_submitter_level_user = User.objects.create(username='project-user-submitter-level')
        self.group.add_user(self.project_submitter_level_user, 'submitter')
        self.project_member_user = User.objects.create(username='project-member-user')
        self.group.add_user(self.project_member_user, 'member')
        self.usergroup.add_user(self.project_member_user, 'privileged')
        self.build = self.project.builds.create(version='1')
        self.userbuild = self.userproject.builds.create(version='1')
        Token.objects.create(user=self.project_privileged_user, key='thekey')
        Token.objects.create(user=self.project_submitter_level_user, key='thesubmitterkey')
        Token.objects.create(user=self.project_member_user, key='memberkey')
        Token.objects.create(user=self.project_admin_user, key='adminkey')

        self.backend = models.Backend.objects.create(name='lava', implementation_type='fake')
        self.client = APIClient('thekey')
        self.submitter_client = APIClient('thesubmitterkey')
        self.restclient = RestAPIClient('thekey')
        self.memberclient = APIClient('memberkey')
        self.adminclient = APIClient('adminkey')

    def test_auth(self):
        self.client.token = 'invalid-token'

        r = self.client.post('/api/submitjob/mygroup/myproject/1/myenv')
        self.assertEqual(403, r.status_code)
        self.assertEqual('User needs permission to submit test jobs.', r.json()['detail'])

        r = self.client.post('/api/watchjob/mygroup/myproject/1/myenv')
        self.assertEqual(403, r.status_code)
        self.assertEqual('User needs permission to submit test jobs.', r.json()['detail'])

    def test_group_project_not_found(self):
        r = self.client.post('/api/submitjob/nonexistentgroup/myproject/1/myenv')
        self.assertEqual(404, r.status_code)
        self.assertEqual('No Group matches the given query.', r.json()['detail'])

        r = self.client.post('/api/submitjob/mygroup/nonexistentproject/1/myenv')
        self.assertEqual(404, r.status_code)
        self.assertEqual('No Project matches the given query.', r.json()['detail'])

    def test_creates_test_run(self):
        args = {
            'backend': 'lava',
            'definition': 'foo: 1',
        }
        r = self.submitter_client.post('/api/submitjob/mygroup/myproject/1/myenv', args)
        self.assertEqual(403, r.status_code)
        r = self.client.post('/api/submitjob/mygroup/myproject/1/myenv', args)
        self.assertEqual(201, r.status_code)
        testjob_queryset = models.TestJob.objects.filter(
            target=self.project,
            environment='myenv',
            target_build=self.build,
            backend=self.backend,
            definition='foo: 1',
        )
        self.assertEqual(
            1,
            testjob_queryset.count()
        )
        logentry_queryset = LogEntry.objects.filter(
            user_id=self.project_privileged_user.pk,
            object_id=testjob_queryset.last().pk
        )
        self.assertEqual(
            1,
            logentry_queryset.count()
        )
        self.assertEqual(
            ADDITION,
            logentry_queryset.last().action_flag
        )

    def test_submitjob_private_group(self):
        args = {
            'backend': 'lava',
            'definition': 'foo: 1',
        }
        r = self.memberclient.post('/api/submitjob/~project-member-user/userproject/1/myenv', args)
        self.assertEqual(201, r.status_code)
        testjob_queryset = models.TestJob.objects.filter(
            target=self.userproject,
            environment='myenv',
            target_build=self.userbuild,
            backend=self.backend,
            definition='foo: 1',
        )
        self.assertEqual(
            1,
            testjob_queryset.count()
        )
        logentry_queryset = LogEntry.objects.filter(
            user_id=self.project_member_user.pk,
            object_id=testjob_queryset.last().pk
        )
        self.assertEqual(
            1,
            logentry_queryset.count()
        )
        self.assertEqual(
            ADDITION,
            logentry_queryset.last().action_flag
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
            'definition': open(twoline_job_definition_file)
        }
        r = self.client.post('/api/submitjob/mygroup/myproject/1/myenv', args)
        self.assertEqual(201, r.status_code)
        testjob = models.TestJob.objects.filter(
            target=self.project,
            environment='myenv',
            target_build=self.build,
            backend=self.backend,
            definition='bar: something\nfoo: 1',
        ).get()
        # when parsing back to yaml, it weirdly adds an extra linebreak at the end
        self.assertEqual('bar: something\nfoo: 1\n', testjob.show_definition)

    @patch("squad.ci.tasks.submit.delay")
    def test_schedules_submission(self, submit):
        args = {
            'backend': 'lava',
            'definition': 'foo: 1',
        }
        r = self.submitter_client.post('/api/submitjob/mygroup/myproject/1/myenv', args)
        self.assertEqual(403, r.status_code)
        self.client.post('/api/submitjob/mygroup/myproject/1/myenv', args)
        job_id = models.TestJob.objects.last().id
        submit.assert_called_with(job_id)

    @patch("squad.ci.tasks.fetch.apply_async")
    def test_auth_on_watch_testjob(self, fetch):
        testjob_id = 1234
        args = {
            'backend': 'lava',
            'testjob_id': testjob_id,
        }
        self.client.token = 'invalid-token'
        r = self.client.post('/api/watchjob/mygroup/myproject/1/myenv', args)
        self.assertEqual(403, r.status_code)

    @patch("squad.ci.tasks.fetch.apply_async")
    def test_watch_testjob(self, fetch):
        testjob_id = 1234
        args = {
            'backend': 'lava',
            'testjob_id': testjob_id,
        }
        r = self.client.post('/api/watchjob/mygroup/myproject/1/myenv', args)
        self.assertEqual(201, r.status_code)
        testjob_queryset = models.TestJob.objects.filter(
            target=self.project,
            environment='myenv',
            target_build=self.build,
            backend=self.backend,
            submitted=True,
            job_id=testjob_id
        )
        self.assertEqual(
            1,
            testjob_queryset.count()
        )
        logentry_queryset = LogEntry.objects.filter(
            user_id=self.project_privileged_user.pk,
            object_id=testjob_queryset.last().pk
        )
        self.assertEqual(
            1,
            logentry_queryset.count()
        )
        self.assertEqual(
            ADDITION,
            logentry_queryset.last().action_flag
        )

    @patch("squad.ci.tasks.fetch.apply_async")
    def test_watch_testjob_private_group(self, fetch):
        testjob_id = 1234
        args = {
            'backend': 'lava',
            'testjob_id': testjob_id,
        }
        r = self.memberclient.post('/api/watchjob/~project-member-user/userproject/1/myenv', args)
        self.assertEqual(201, r.status_code)
        testjob_queryset = models.TestJob.objects.filter(
            target=self.userproject,
            environment='myenv',
            target_build=self.userbuild,
            backend=self.backend,
            submitted=True,
            job_id=testjob_id
        )
        self.assertEqual(
            1,
            testjob_queryset.count()
        )
        logentry_queryset = LogEntry.objects.filter(
            user_id=self.project_member_user.pk,
            object_id=testjob_queryset.last().pk
        )
        self.assertEqual(
            1,
            logentry_queryset.count()
        )
        self.assertEqual(
            ADDITION,
            logentry_queryset.last().action_flag
        )

    @patch("squad.ci.tasks.fetch.apply_async")
    def test_watch_testjob_mising_id(self, fetch):
        args = {
            'backend': 'lava'
        }
        r = self.client.post('/api/watchjob/mygroup/myproject/1/myenv', args)
        self.assertEqual(400, r.status_code)

    @patch('squad.ci.models.Backend.get_implementation')
    def test_resubmit_submitter(self, get_implementation):
        impl = MagicMock()
        impl.resubmit = MagicMock()
        get_implementation.return_value = impl

        t = self.backend.test_jobs.create(
            target=self.project,
            can_resubmit=True
        )
        r = self.client.post('/api/resubmit/%s' % t.pk)
        self.assertEqual(201, r.status_code)
        impl.resubmit.assert_called()
        t.refresh_from_db()
        self.assertEqual(False, t.can_resubmit)

    @patch('squad.ci.models.Backend.get_implementation')
    def test_resubmit_submitter_cant_resubmit(self, get_implementation):
        impl = MagicMock()
        impl.resubmit = MagicMock()
        get_implementation.return_value = impl

        t = self.backend.test_jobs.create(
            target=self.project,
            can_resubmit=False
        )
        r = self.client.post('/api/resubmit/%s' % t.pk)
        self.assertEqual(403, r.status_code)
        impl.resubmit.assert_not_called()
        t.refresh_from_db()
        self.assertEqual(False, t.can_resubmit)

    @patch('squad.ci.models.Backend.get_implementation')
    def test_resubmit_submitter_token_auth(self, get_implementation):
        impl = MagicMock()
        impl.resubmit = MagicMock()
        get_implementation.return_value = impl

        t = self.backend.test_jobs.create(
            target=self.project,
            can_resubmit=True
        )

        r = self.restclient.post('/api/resubmit/%s' % t.pk)
        self.assertEqual(201, r.status_code)
        impl.resubmit.assert_called()
        t.refresh_from_db()
        self.assertEqual(False, t.can_resubmit)

    @patch('squad.ci.models.Backend.get_implementation')
    def test_resubmit_submitter_auth_token_cant_resubmit(self, get_implementation):
        impl = MagicMock()
        impl.resubmit = MagicMock()
        get_implementation.return_value = impl

        t = self.backend.test_jobs.create(
            target=self.project,
            can_resubmit=False
        )

        r = self.restclient.post('/api/resubmit/%s' % t.pk)
        self.assertEqual(403, r.status_code)
        impl.resubmit.assert_not_called()
        t.refresh_from_db()
        self.assertEqual(False, t.can_resubmit)

    @patch('squad.ci.models.Backend.get_implementation')
    def test_force_resubmit_submitter_token_auth(self, get_implementation):
        impl = MagicMock()
        impl.resubmit = MagicMock()
        get_implementation.return_value = impl

        t = self.backend.test_jobs.create(
            target=self.project,
            can_resubmit=True
        )

        r = self.restclient.post('/api/resubmit/%s' % t.pk)
        self.assertEqual(201, r.status_code)
        impl.resubmit.assert_called()
        t.refresh_from_db()
        self.assertEqual(False, t.can_resubmit)

    @patch('squad.ci.models.Backend.get_implementation')
    def test_resubmit_admin(self, get_implementation):
        impl = MagicMock()
        impl.resubmit = MagicMock()
        get_implementation.return_value = impl

        t = self.backend.test_jobs.create(
            target=self.project,
            can_resubmit=True
        )
        r = self.adminclient.post('/api/resubmit/%s' % t.pk)
        self.assertEqual(201, r.status_code)
        impl.resubmit.assert_called()
        t.refresh_from_db()
        self.assertEqual(False, t.can_resubmit)

    def test_disallowed_resubmit(self):
        t = self.backend.test_jobs.create(
            target=self.project,
            can_resubmit=True
        )
        r = self.memberclient.post('/api/resubmit/%s' % t.pk)
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

        r = client.post('/api/resubmit/999')
        self.assertEqual(404, r.status_code)

    @patch('squad.ci.models.TestJob.resubmit', side_effect=SubmissionIssue('BOOM'))
    def test_resubmit_error(self, resubmit):
        t = self.backend.test_jobs.create(
            target=self.project,
            can_resubmit=True
        )
        r = self.adminclient.post('/api/resubmit/%s' % t.pk)
        self.assertEqual(500, r.status_code)
        self.assertEqual('BOOM', r.content.decode())
