import os
from io import StringIO


from django.contrib.auth.models import User
from django.contrib.admin.models import LogEntry, ADDITION
from django.test import TestCase
from django.test import Client
from django.utils.encoding import force_text
from test.api import APIClient


from squad.core import models
from rest_framework.authtoken.models import Token


tests_file = os.path.join(os.path.dirname(__file__), 'tests.json')
tests_two_file = os.path.join(os.path.dirname(__file__), 'tests_two.json')
tests_log_file = os.path.join(os.path.dirname(__file__), 'tests_log.json')
metrics_file = os.path.join(os.path.dirname(__file__), 'benchmarks.json')
log_file = os.path.join(os.path.dirname(__file__), 'test_run.log')
metadata_file = os.path.join(os.path.dirname(__file__), 'metadata.json')


def invalid_json():
    return StringIO('{')


class ApiTest(TestCase):

    def setUp(self):

        self.group = models.Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.usergroup = models.UserNamespace.objects.create(slug='~project-user')
        self.userproject = self.usergroup.projects.create(slug='userproject')
        self.project_submission_admin_user = User.objects.create(username='project-user')
        self.project_submitter_level = User.objects.create(username='project-user-two')
        self.group.add_admin(self.project_submission_admin_user)
        self.group.add_user(self.project_submitter_level, 'submitter')
        self.usergroup.add_admin(self.project_submission_admin_user)
        Token.objects.create(user=self.project_submission_admin_user, key='thekey')
        Token.objects.create(user=self.project_submitter_level, key='thesubmitterkey')

        self.global_submission_user = User.objects.create(username='global-user', is_staff=True)
        self.global_token = Token.objects.create(user=self.global_submission_user)

        self.client = APIClient('thekey')
        self.submitter_client = APIClient('thesubmitterkey')


class CreateTestRunApiTest(ApiTest):

    def test_create_object_hierarchy(self):
        response = self.client.post('/api/submit/mygroup/myproject/1.0.0/myenvironment')
        self.assertEqual(response.status_code, 201)

        build = self.project.builds.get(version='1.0.0')
        environment = self.project.environments.get(slug='myenvironment')
        testrun = build.test_runs.get(environment=environment)
        logentry_queryset = LogEntry.objects.filter(
            user_id=self.project_submission_admin_user.pk,
            object_id=testrun.pk,
            object_repr=force_text(testrun),
        )
        self.assertEqual(
            1,
            logentry_queryset.count()
        )
        self.assertEqual(
            ADDITION,
            logentry_queryset.last().action_flag
        )

    def test_create_object_hierarchy_private(self):
        response = self.client.post('/api/submit/~project-user/userproject/1.0.0/myenvironment')
        self.assertEqual(response.status_code, 201)

        self.userproject.builds.get(version='1.0.0')
        self.userproject.environments.get(slug='myenvironment')

    def test_create_test_run(self):
        test_runs = models.TestRun.objects.count()
        self.client.post('/api/submit/mygroup/myproject/1.0.22/myenvironment')
        self.submitter_client.post('/api/submit/mygroup/myproject/1.0.23/myenvironment2')
        self.assertEqual(test_runs + 2, models.TestRun.objects.count())

    def test_receives_tests_file(self):
        with open(tests_file) as f:
            self.client.post(
                '/api/submit/mygroup/myproject/1.0.1/myenvironment',
                {'tests': f}
            )
        self.assertIsNotNone(models.TestRun.objects.last().tests_file)
        self.assertIsNotNone(models.TestRun.objects.last().tests_file_storage)
        self.assertNotEqual(0, models.Test.objects.count())
        self.assertIsNone(models.Test.objects.last().log)
        with open(tests_two_file) as f:
            self.submitter_client.post(
                '/api/submit/mygroup/myproject/1.1.5/myenvironment3',
                {'tests': f}
            )
        self.assertIsNotNone(models.TestRun.objects.last().tests_file)
        self.assertIsNotNone(models.TestRun.objects.last().tests_file_storage)
        self.assertNotEqual(0, models.Test.objects.count())
        self.assertIsNone(models.Test.objects.last().log)

    def test_receives_tests_file_with_logs(self):
        with open(tests_log_file) as f:
            self.client.post(
                '/api/submit/mygroup/myproject/1.0.2/myenvironment',
                {'tests': f}
            )
        self.assertIsNotNone(models.TestRun.objects.last().tests_file)
        self.assertIsNotNone(models.TestRun.objects.last().tests_file_storage)
        self.assertNotEqual(0, models.Test.objects.count())
        test_one = models.Test.objects.filter(metadata__name="test_one").first()
        test_two = models.Test.objects.filter(metadata__name="test_two").first()
        self.assertTrue(test_one.result)
        self.assertFalse(test_two.result)
        self.assertEqual("test one log", test_one.log)
        self.assertEqual("test two log", test_two.log)

    def test_receives_tests_file_as_POST_param(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.3/myenvironment',
            {'tests': '{"test1": "pass"}'}
        )
        self.assertIsNotNone(models.TestRun.objects.last().tests_file)
        self.assertIsNotNone(models.TestRun.objects.last().tests_file_storage)
        self.assertNotEqual(0, models.Test.objects.count())
        self.assertIsNone(models.Test.objects.last().log)
        self.submitter_client.post(
            '/api/submit/mygroup/myproject/1.1.3/myenvironment3',
            {'tests': '{"submitterTest": "pass"}'}
        )
        self.assertIsNotNone(models.TestRun.objects.last().tests_file)
        self.assertIsNotNone(models.TestRun.objects.last().tests_file_storage)
        self.assertNotEqual(0, models.Test.objects.count())
        self.assertIsNone(models.Test.objects.last().log)

    def test_receives_tests_file_as_POST_param_with_logs(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.4/myenvironment',
            {'tests': '{"test1": {"result": "pass", "log": "test log"}}'}
        )
        self.assertIsNotNone(models.TestRun.objects.last().tests_file)
        self.assertIsNotNone(models.TestRun.objects.last().tests_file_storage)
        self.assertNotEqual(0, models.Test.objects.count())
        self.assertIsNotNone(models.Test.objects.last().log)
        test1 = models.Test.objects.filter(metadata__name="test1").first()
        self.assertTrue(test1.result)
        self.assertEqual("test log", test1.log)

    def test_receives_metrics_file(self):
        with open(metrics_file) as f:
            self.client.post(
                '/api/submit/mygroup/myproject/1.0.5/myenvironment',
                {'metrics': f}
            )
        self.assertIsNotNone(models.TestRun.objects.last().metrics_file)
        self.assertIsNotNone(models.TestRun.objects.last().metrics_file_storage)
        self.assertNotEqual(0, models.Metric.objects.count())

    def test_receives_metrics_file_as_POST_param_with_no_metric_unit(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.6/myenvironment',
            {'metrics': '{"metric1": 10}'}
        )
        self.assertIsNotNone(models.TestRun.objects.last().metrics_file)
        self.assertIsNotNone(models.TestRun.objects.last().metrics_file_storage)
        self.assertNotEqual(0, models.Metric.objects.count())

    def test_receives_metrics_file_as_POST_param(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.6/myenvironment',
            {'metrics': '{"metric1": {"value": 10, "unit": ""}}'}
        )
        self.assertIsNotNone(models.TestRun.objects.last().metrics_file)
        self.assertIsNotNone(models.TestRun.objects.last().metrics_file_storage)
        self.assertNotEqual(0, models.Metric.objects.count())

    def test_receives_log_file(self):
        with open(log_file) as f:
            self.client.post('/api/submit/mygroup/myproject/1.0.7/myenvironment',
                             {'log': f})
        self.assertIsNotNone(models.TestRun.objects.last().log_file)
        self.assertIsNotNone(models.TestRun.objects.last().log_file_storage)

    def test_receives_log_file_as_POST_param(self):
        self.client.post('/api/submit/mygroup/myproject/1.0.8/myenvironment',
                         {'log': "THIS IS THE LOG"})
        self.assertIsNotNone(models.TestRun.objects.last().log_file)
        self.assertIsNotNone(models.TestRun.objects.last().log_file_storage)

    def test_process_data_on_submission(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.9/myenvironment',
            {
                'tests': open(tests_file),
                'metrics': open(metrics_file),
            }
        )
        self.assertNotEqual(0, models.Test.objects.count())
        self.assertNotEqual(0, models.Metric.objects.count())
        self.assertNotEqual(0, models.Status.objects.count())

    def test_receives_metadata_file(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.10/myenvironment',
            {
                'metadata': open(metadata_file),
            }
        )
        t = models.TestRun.objects.last()
        self.assertEqual("2016-09-01T00:00:00+00:00", t.datetime.isoformat())

    def test_receives_metadata_file_as_POST_param(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.11/myenvironment',
            {
                'metadata': '{"job_id": "123", "datetime": "2016-09-01T00:00:00+00:00"}',
            }
        )
        t = models.TestRun.objects.last()
        self.assertEqual("2016-09-01T00:00:00+00:00", t.datetime.isoformat())

    def test_receives_metadata_fields_as_POST_params(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.12/myenvironment',
            {
                "build_url": "http://example.com/build/1",
                "datetime": "2016-09-01T00:00:00+00:00",
                "job_id": "123",
                "job_status": "Complete",
                "job_url": "http://example.com/build/1/jobs/1",
                "resubmit_url": "http://example.com/build/1/jobs/1/resubmit",
            }
        )

        t = models.TestRun.objects.last()
        self.assertEqual("2016-09-01T00:00:00+00:00", t.datetime.isoformat())
        self.assertIsNotNone(t.build_url)
        self.assertIsNotNone(t.job_id)
        self.assertIsNotNone(t.job_status)
        self.assertIsNotNone(t.job_url)
        self.assertIsNotNone(t.resubmit_url)

    def test_stores_metadata_file(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.13/myenvironment',
            {
                'metadata': open(metadata_file),
            }
        )
        t = models.TestRun.objects.last()
        self.assertEqual(open(metadata_file).read(), t.metadata_file)

    def test_attachment(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.14/myenvironment',
            {
                'attachment': open(metadata_file),
            }
        )
        t = models.TestRun.objects.last()
        attachment = t.attachments.first()
        self.assertEqual(open(metadata_file, mode='rb').read(), bytes(attachment.data))
        self.assertEqual(open(metadata_file, mode='rb').read(), attachment.storage.read())

    def test_multiple_attachments(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.15/myenvironment',
            {
                'attachment': [
                    open(metadata_file),
                    open(log_file),
                ]
            }
        )
        t = models.TestRun.objects.last()
        attachment_metadata = t.attachments.get(filename=os.path.basename(metadata_file))
        attachment_log = t.attachments.get(filename=os.path.basename(log_file))

        self.assertIsNotNone(attachment_metadata)
        self.assertIsNotNone(attachment_metadata.storage)
        self.assertIsNotNone(attachment_log)
        self.assertIsNotNone(attachment_log.storage)

    def test_unauthorized(self):
        client = Client()  # regular client without auth support
        response = client.post('/api/submit/mygroup/myproject/1.0.0/myenvironment')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(models.TestRun.objects.count(), 0)

    def test_wrong_token(self):
        self.client.token = 'wrongtoken'
        response = self.client.post('/api/submit/mygroup/myproject/1.0.0/myenv')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(models.TestRun.objects.count(), 0)

    def test_good_token_but_non_member_on_private_project(self):
        non_member = User.objects.create(username='nonmember')
        Token.objects.create(user=non_member, key='nonmemberkey')
        self.project.is_public = False
        self.project.save()
        client = APIClient('nonmemberkey')
        response = client.post('/api/submit/mygroup/myproject/1.0.0/myenvironment')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(models.TestRun.objects.count(), 0)

    def test_good_token_but_non_member(self):
        non_member = User.objects.create(username='nonmember')
        Token.objects.create(user=non_member, key='nonmemberkey')
        client = APIClient('nonmemberkey')
        response = client.post('/api/submit/mygroup/myproject/1.0.0/myenvironment')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(models.TestRun.objects.count(), 0)

    def test_good_token_but_member_without_submit_access(self):
        member = User.objects.create(username='member')
        self.group.add_user(member)
        Token.objects.create(user=member, key='memberkey')
        client = APIClient('memberkey')
        response = client.post('/api/submit/mygroup/myproject/1.0.0/myenvironment')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(models.TestRun.objects.count(), 0)

    def test_good_token_for_member_with_submit_access(self):
        member = User.objects.create(username='member')
        self.group.add_user(member, 'submitter')
        Token.objects.create(user=member, key='memberkey')
        client = APIClient('memberkey')
        response = client.post('/api/submit/mygroup/myproject/1.0.16/myenvironment')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(models.TestRun.objects.count(), 1)

    def test_auth_with_global_token(self):
        self.client.token = self.global_token.key
        response = self.client.post('/api/submit/mygroup/myproject/1.0.17/myenvironment')
        self.assertEqual(201, response.status_code)
        self.assertEqual(1, models.TestRun.objects.count())

    def test_404_on_non_existing_group(self):
        response = self.client.post('/api/submit/mygrouppp/myproject/1.0.0/myenv')
        self.assertEqual(404, response.status_code)

    def test_404_on_non_existing_project(self):
        response = self.client.post('/api/submit/mygroup/myprojectttt/1.0.0/myenv')
        self.assertEqual(404, response.status_code)

    def test_invalid_metrics_json(self):
        response = self.client.post(
            '/api/submit/mygroup/myproject/1.0.0/myenvironment',
            {
                'metrics': invalid_json(),
            }
        )
        self.assertEqual(400, response.status_code)

    def test_invalid_tests_json(self):
        response = self.client.post(
            '/api/submit/mygroup/myproject/1.0.0/myenvironment',
            {
                'tests': invalid_json(),
            }
        )
        self.assertEqual(400, response.status_code)

    def test_invalid_metadata_json(self):
        response = self.client.post(
            '/api/submit/mygroup/myproject/1.0.0/myenvironment',
            {
                'metadata': invalid_json(),
            }
        )
        self.assertEqual(400, response.status_code)

    def test_reject_submission_without_job_id(self):
        response = self.client.post(
            '/api/submit/mygroup/myproject/1.0.18/myenvironment',
            {
                'metadata': StringIO('{"datetime": "2016-09-01T00:00:00+00:00"}'),
            }
        )
        self.assertEqual(201, response.status_code)

    def test_reject_submission_with_existing_job_id(self):
        def post():
            return self.client.post(
                '/api/submit/mygroup/myproject/1.0.19/myenvironment',
                {
                    'metadata': open(metadata_file),
                }
            )

        first = post()
        second = post()

        self.assertEqual(201, first.status_code)
        self.assertEqual(400, second.status_code)

    def test_reject_submission_with_int_job_id(self):
        response = self.client.post('/api/submit/mygroup/myproject/1.0.20/myenvironment', {'metadata': '{"job_id": 123}'})
        self.assertEqual(201, response.status_code)

    def test_accepts_uppercase_in_slug(self):
        self.group.slug = 'MyGroup'
        self.group.save()
        self.project.slug = 'MyProject'
        self.project.save()
        response = self.client.post('/api/submit/MyGroup/MyProject/1.0.21/MyEnvironment')
        self.assertEqual(response.status_code, 201)


class CreateBuildApiTest(ApiTest):

    def setUp(self):
        super(CreateBuildApiTest, self).setUp()
        self.github = models.PatchSource.objects.create(
            name='github',
            username='foo',
            url='https://github.com/',
            token='*********',
            implementation='example'
        )

    def test_patch_source(self):
        response = self.client.post(
            '/api/createbuild/mygroup/myproject/1.0.0',
            {
                'patch_source': 'github',
                'patch_id': '999',
            }
        )
        self.assertEqual(response.status_code, 201)

        build = self.project.builds.get(version='1.0.0')
        self.assertEqual(self.github, build.patch_source)
        self.assertEqual(build.patch_id, "999")
        logentry_queryset = LogEntry.objects.filter(
            user_id=self.project_submission_admin_user.pk,
            object_id=build.pk,
            object_repr=force_text(build),
        )
        self.assertEqual(
            1,
            logentry_queryset.count()
        )
        self.assertEqual(
            ADDITION,
            logentry_queryset.last().action_flag
        )

    def test_patch_source_private(self):
        response = self.client.post(
            '/api/createbuild/~project-user/userproject/1.0.0',
            {
                'patch_source': 'github',
                'patch_id': '999',
            }
        )
        self.assertEqual(response.status_code, 201)

        build = self.userproject.builds.get(version='1.0.0')
        self.assertEqual(self.github, build.patch_source)
        self.assertEqual(build.patch_id, "999")

    def test_patch_baseline(self):
        baseline = self.project.builds.create(version='0')
        response = self.client.post(
            '/api/createbuild/mygroup/myproject/1',
            {
                'patch_source': 'github',
                'patch_id': '999',
                'patch_baseline': '0',
            }
        )
        self.assertEqual(response.status_code, 201)

        build = self.project.builds.get(version='1')
        self.assertEqual(build.patch_baseline, baseline)

    def test_unexisting_patch_source(self):
        response = self.client.post(
            '/api/createbuild/mygroup/myproject/1.0.0',
            {
                'patch_source': 'foobarbaz',  # does not exist
                'patch_id': '999',
            }
        )
        self.assertEqual(response.status_code, 400)

    def test_create_callback(self):
        response = self.client.post(
            '/api/createbuild/mygroup/myproject/with-callback',
            {
                'callback_url': 'http://the-callback.target'
            }
        )
        self.assertEqual(response.status_code, 201)

        build = self.project.builds.get(version='with-callback')
        self.assertEqual(1, build.callbacks.count())

    def test_create_callback_all_attrs(self):
        attrs = {
            'url': 'http://the-callback.target.com',
            'method': 'post',
            'event': 'on_build_finished',
            'headers': '{"Authorization": "123456"}',
            'payload': '{"data": "value"}',
            'payload_is_json': 'true',
            'record_response': 'true',
        }
        response = self.client.post(
            '/api/createbuild/mygroup/myproject/with-callback',
            {
                'callback_%s' % attr: attrs[attr] for attr in attrs.keys()
            }
        )
        self.assertEqual(response.status_code, 201)

        build = self.project.builds.get(version='with-callback')
        self.assertEqual(1, build.callbacks.count())

        callback = build.callbacks.first()
        attrs['payload_is_json'] = True
        attrs['record_response'] = True
        for attr in attrs:
            self.assertEqual(getattr(callback, attr), attrs[attr])

    def test_malformed_callback(self):
        response = self.client.post(
            '/api/createbuild/mygroup/myproject/with-callback',
            {
                'callback_url': 'invalid-callback-target-url'
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(b'Enter a valid URL.', response.content)

    def test_duplicated_callback(self):
        callback_url = 'http://the-callback.target'
        response = self.client.post(
            '/api/createbuild/mygroup/myproject/with-callback',
            {
                'callback_url': callback_url,
            }
        )
        self.assertEqual(response.status_code, 201)
        build = self.project.builds.get(version='with-callback')
        self.assertEqual(1, build.callbacks.count())

        response = self.client.post(
            '/api/createbuild/mygroup/myproject/with-callback',
            {
                'callback_url': callback_url,
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(1, build.callbacks.count())
        self.assertEqual(b'Callback with this Object reference type, Object reference id, Url and Event already exists.', response.content)
