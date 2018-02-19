import os
from io import StringIO


from django.contrib.auth.models import User
from django.test import TestCase
from django.test import Client
from test.api import APIClient


from squad.core import models
from rest_framework.authtoken.models import Token


tests_file = os.path.join(os.path.dirname(__file__), 'tests.json')
metrics_file = os.path.join(os.path.dirname(__file__), 'benchmarks.json')
log_file = os.path.join(os.path.dirname(__file__), 'test_run.log')
metadata_file = os.path.join(os.path.dirname(__file__), 'metadata.json')


def invalid_json():
    return StringIO('{')


class ApiTest(TestCase):

    def setUp(self):

        self.group = models.Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.project_submission_user = User.objects.create(username='project-user')
        usergroup = self.group.user_groups.create()
        self.project_submission_user.groups.add(usergroup)
        Token.objects.create(user=self.project_submission_user, key='thekey')

        self.global_submission_user = User.objects.create(username='global-user', is_staff=True)
        self.global_token = Token.objects.create(user=self.global_submission_user)

        self.client = APIClient('thekey')

    def test_create_object_hierarchy(self):
        response = self.client.post('/api/submit/mygroup/myproject/1.0.0/myenvironment')
        self.assertEqual(response.status_code, 201)

        self.project.builds.get(version='1.0.0')
        self.project.environments.get(slug='myenvironment')

    def test_create_test_run(self):
        test_runs = models.TestRun.objects.count()
        self.client.post('/api/submit/mygroup/myproject/1.0.0/myenvironment')
        self.assertEqual(test_runs + 1, models.TestRun.objects.count())

    def test_receives_tests_file(self):
        with open(tests_file) as f:
            self.client.post(
                '/api/submit/mygroup/myproject/1.0.0/myenvironment',
                {'tests': f}
            )
        self.assertIsNotNone(models.TestRun.objects.last().tests_file)
        self.assertNotEqual(0, models.Test.objects.count())

    def test_receives_tests_file_as_POST_param(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.0/myenvironment',
            {'tests': '{"test1": "pass"}'}
        )
        self.assertIsNotNone(models.TestRun.objects.last().tests_file)
        self.assertNotEqual(0, models.Test.objects.count())

    def test_receives_metrics_file(self):
        with open(metrics_file) as f:
            self.client.post(
                '/api/submit/mygroup/myproject/1.0.0/myenvironment',
                {'metrics': f}
            )
        self.assertIsNotNone(models.TestRun.objects.last().metrics_file)
        self.assertNotEqual(0, models.Metric.objects.count())

    def test_receives_metrics_file_as_POST_param(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.0/myenvironment',
            {'metrics': '{"metric1": 10}'}
        )
        self.assertIsNotNone(models.TestRun.objects.last().metrics_file)
        self.assertNotEqual(0, models.Metric.objects.count())

    def test_receives_log_file(self):
        with open(log_file) as f:
            self.client.post('/api/submit/mygroup/myproject/1.0.0/myenvironment',
                             {'log': f})
        self.assertIsNotNone(models.TestRun.objects.last().log_file)

    def test_receives_log_file_as_POST_param(self):
        self.client.post('/api/submit/mygroup/myproject/1.0.0/myenvironment',
                         {'log': "THIS IS THE LOG"})
        self.assertIsNotNone(models.TestRun.objects.last().log_file)

    def test_process_data_on_submission(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.0/myenvironment',
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
            '/api/submit/mygroup/myproject/1.0.0/myenvironment',
            {
                'metadata': open(metadata_file),
            }
        )
        t = models.TestRun.objects.last()
        self.assertEqual("2016-09-01T00:00:00+00:00", t.datetime.isoformat())

    def test_receives_metadata_file_as_POST_param(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.0/myenvironment',
            {
                'metadata': '{"job_id": "123", "datetime": "2016-09-01T00:00:00+00:00"}',
            }
        )
        t = models.TestRun.objects.last()
        self.assertEqual("2016-09-01T00:00:00+00:00", t.datetime.isoformat())

    def test_receives_metadata_fields_as_POST_params(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.0/myenvironment',
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
            '/api/submit/mygroup/myproject/1.0.0/myenvironment',
            {
                'metadata': open(metadata_file),
            }
        )
        t = models.TestRun.objects.last()
        self.assertEqual(open(metadata_file).read(), t.metadata_file)

    def test_attachment(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.0/myenvironment',
            {
                'attachment': open(metadata_file),
            }
        )
        t = models.TestRun.objects.last()
        attachment = t.attachments.first()
        self.assertEqual(open(metadata_file, mode='rb').read(), bytes(attachment.data))

    def test_multiple_attachments(self):
        self.client.post(
            '/api/submit/mygroup/myproject/1.0.0/myenvironment',
            {
                'attachment': [
                    open(metadata_file),
                    open(log_file),
                ]
            }
        )
        t = models.TestRun.objects.last()
        self.assertIsNotNone(t.attachments.get(filename=os.path.basename(metadata_file)))
        self.assertIsNotNone(t.attachments.get(filename=os.path.basename(log_file)))

    def test_unauthorized(self):
        client = Client()  # regular client without auth support
        response = client.post('/api/submit/mygroup/myproject/1.0.0/myenvironment')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(models.TestRun.objects.count(), 0)

    def test_wrong_token(self):
        self.client.token = 'wrongtoken'
        response = self.client.post('/api/submit/mygroup/myproject/1.0.0/myenv')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(models.TestRun.objects.count(), 0)

    def test_auth_with_global_token(self):
        self.client.token = self.global_token.key
        response = self.client.post('/api/submit/mygroup/myproject/1.0.0/myenvironment')
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
            '/api/submit/mygroup/myproject/1.0.0/myenvironment',
            {
                'metadata': StringIO('{"datetime": "2016-09-01T00:00:00+00:00"}'),
            }
        )
        self.assertEqual(400, response.status_code)

    def test_reject_submission_with_existing_job_id(self):
        def post():
            return self.client.post(
                '/api/submit/mygroup/myproject/1.0.0/myenvironment',
                {
                    'metadata': open(metadata_file),
                }
            )

        first = post()
        second = post()

        self.assertEqual(201, first.status_code)
        self.assertEqual(400, second.status_code)

    def test_accepts_uppercase_in_slug(self):
        self.group.slug = 'MyGroup'
        self.group.save()
        self.project.slug = 'MyProject'
        self.project.save()
        response = self.client.post('/api/submit/MyGroup/MyProject/1.0.0/MyEnvironment')
        self.assertEqual(response.status_code, 201)
