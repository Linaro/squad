import json
from test.api import APIClient
from django.test import TestCase
from squad.core import models
from squad.core.tasks import UpdateProjectStatus
from squad.ci import models as ci_models


class RestApiTest(TestCase):

    def setUp(self):
        self.group = models.Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.build = self.project.builds.create(version='1')
        self.environment = self.project.environments.create(slug='myenv')
        self.testrun = self.build.test_runs.create(environment=self.environment, build=self.build)
        self.backend = ci_models.Backend.objects.create(name='foobar')
        self.testjob = self.build.test_jobs.create(
            definition="foo: bar",
            backend=self.backend,
            target=self.project,
            target_build=self.build,
            build='1',
            environment='myenv',
            testrun=self.testrun
        )
        self.emailtemplate = models.EmailTemplate.objects.create(
            name="fooTemplate",
            subject="abc",
            plain_text="def",
        )

    def hit(self, url):
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        text = response.content.decode('utf-8')
        if response['Content-Type'] == 'application/json':
            return json.loads(text)
        else:
            return text

    def test_root(self):
        self.hit('/api/')

    def test_projects(self):
        data = self.hit('/api/projects/')
        self.assertEqual(1, len(data['results']))

    def test_project_builds(self):
        data = self.hit('/api/projects/%d/builds/' % self.project.id)
        self.assertEqual(1, len(data['results']))

    def test_builds(self):
        data = self.hit('/api/builds/')
        self.assertEqual(1, len(data['results']))

    def test_builds_status(self):
        response = self.client.get('/api/builds/%d/status/')
        self.assertEqual(404, response.status_code)
        # create ProjectStatus
        UpdateProjectStatus()(self.testrun)
        self.hit('/api/builds/%d/status/' % self.build.id)

    def test_build_testruns(self):
        data = self.hit('/api/builds/%d/testruns/' % self.build.id)
        self.assertEqual(1, len(data['results']))

    def test_build_testjobs(self):
        data = self.hit('/api/builds/%d/testjobs/' % self.build.id)
        self.assertEqual(1, len(data['results']))

    def test_testjob(self):
        data = self.hit('/api/testjobs/%d/' % self.testjob.id)
        self.assertEqual('myenv', data['environment'])

    def test_testjob_definition(self):
        data = self.hit('/api/testjobs/%d/definition/' % self.testjob.id)
        self.assertEqual('foo: bar', data)

    def test_backends(self):
        data = self.hit('/api/backends/')
        self.assertEqual('foobar', data['results'][0]['name'])

    def test_environments(self):
        data = self.hit('/api/environments/')
        self.assertEqual('myenv', data['results'][0]['slug'])

    def test_email_template(self):
        data = self.hit('/api/emailtemplates/')
        self.assertEqual('fooTemplate', data['results'][0]['name'])
