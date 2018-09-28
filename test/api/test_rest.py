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
        self.build2 = self.project.builds.create(version='2')
        self.build3 = self.project.builds.create(version='3')
        self.environment = self.project.environments.create(slug='myenv')
        self.testrun = self.build.test_runs.create(environment=self.environment, build=self.build)
        self.testrun2 = self.build2.test_runs.create(environment=self.environment, build=self.build2)
        self.testrun3 = self.build3.test_runs.create(environment=self.environment, build=self.build3)
        self.backend = ci_models.Backend.objects.create(name='foobar')
        self.patchsource = models.PatchSource.objects.create(name='baz_source', username='u', url='http://example.com', token='secret')
        self.knownissue = models.KnownIssue.objects.create(title='knownissue_foo', test_name='test/bar', active=True)
        self.knownissue.environments.add(self.environment)

        self.testjob = self.build.test_jobs.create(
            definition="foo: bar",
            backend=self.backend,
            target=self.project,
            target_build=self.build,
            build='1',
            environment='myenv',
            testrun=self.testrun
        )
        self.testjob2 = self.build.test_jobs.create(
            definition="foo: bar",
            backend=self.backend,
            target=self.project,
            target_build=self.build2,
            build='2',
            environment='myenv',
            testrun=self.testrun2
        )
        self.testjob3 = self.build.test_jobs.create(
            definition="foo: bar",
            backend=self.backend,
            target=self.project,
            target_build=self.build3,
            build='3',
            environment='myenv',
            testrun=self.testrun3
        )
        self.emailtemplate = models.EmailTemplate.objects.create(
            name="fooTemplate",
            subject="abc",
            plain_text="def",
        )
        self.validemailtemplate = models.EmailTemplate.objects.create(
            name="validTemplate",
            subject="subject",
            plain_text="{% if foo %}bar{% endif %}",
            html="{% if foo %}bar{% endif %}"
        )
        self.invalidemailtemplate = models.EmailTemplate.objects.create(
            name="invalidTemplate",
            subject="subject",
            plain_text="{% if foo %}bar",
            html="{% if foo %}bar"
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
        self.assertEqual(3, len(data['results']))

    def test_builds(self):
        data = self.hit('/api/builds/')
        self.assertEqual(3, len(data['results']))

    def test_builds_status(self):
        response = self.client.get('/api/builds/%d/status/' % self.build.id)
        self.assertEqual(404, response.status_code)
        # create ProjectStatus
        UpdateProjectStatus()(self.testrun)
        self.hit('/api/builds/%d/status/' % self.build.id)

    def test_builds_email(self):
        response = self.client.get('/api/builds/%d/email/' % self.build.id)
        self.assertEqual(404, response.status_code)
        # create ProjectStatus
        UpdateProjectStatus()(self.testrun)
        self.hit('/api/builds/%d/email/' % self.build.id)

    def test_builds_email_custom_template(self):
        response = self.client.get('/api/builds/%d/email/?template=%s' % (self.build.id, self.validemailtemplate.pk))
        self.assertEqual(404, response.status_code)
        # create ProjectStatus
        UpdateProjectStatus()(self.testrun)
        response = self.client.get('/api/builds/%d/email/?template=%s' % (self.build.id, self.validemailtemplate.pk))
        self.assertEqual(200, response.status_code)
        self.assertEqual("text/plain", response['Content-Type'])

    def test_builds_email_custom_invalid_template(self):
        response = self.client.get('/api/builds/%d/email/?template=%s' % (self.build.id, self.invalidemailtemplate.pk))
        self.assertEqual(404, response.status_code)
        # create ProjectStatus
        UpdateProjectStatus()(self.testrun)
        response = self.client.get('/api/builds/%d/email/?template=%s' % (self.build.id, self.invalidemailtemplate.pk))
        self.assertEqual(500, response.status_code)

    def test_builds_email_custom_baseline(self):
        UpdateProjectStatus()(self.testrun)
        UpdateProjectStatus()(self.testrun3)
        self.hit('/api/builds/%d/email/?baseline=%s' % (self.build.id, self.build3.id))

    def test_builds_email_custom_baseline_missing_status(self):
        UpdateProjectStatus()(self.testrun)
        response = self.client.get('/api/builds/%d/email/?baseline=%s' % (self.build.id, self.build2.id))
        self.assertEqual(500, response.status_code)

    def test_builds_email_custom_invalid_baseline(self):
        UpdateProjectStatus()(self.testrun)
        response = self.client.get('/api/builds/%d/email/?baseline=999' % (self.build.id))
        self.assertEqual(500, response.status_code)

    def test_build_testruns(self):
        data = self.hit('/api/builds/%d/testruns/' % self.build.id)
        self.assertEqual(1, len(data['results']))

    def test_build_testjobs(self):
        data = self.hit('/api/builds/%d/testjobs/' % self.build.id)
        self.assertEqual(1, len(data['results']))

    def test_testjob(self):
        data = self.hit('/api/testjobs/%d/' % self.testjob.id)
        self.assertEqual('myenv', data['environment'])

    def test_testruns(self):
        data = self.hit('/api/testruns/%d/' % self.testrun.id)
        self.assertEqual(self.testrun.id, data['id'])

    def test_testruns_tests(self):
        data = self.hit('/api/testruns/%d/tests/' % self.testrun.id)
        self.assertEqual(list, type(data['results']))

    def test_testruns_metrics(self):
        data = self.hit('/api/testruns/%d/metrics/' % self.testrun.id)
        self.assertEqual(list, type(data['results']))

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

    def test_groups(self):
        data = self.hit('/api/groups/')
        self.assertEqual('mygroup', data['results'][0]['slug'])

    def test_patch_source(self):
        data = self.hit('/api/patchsources/')
        self.assertEqual(1, len(data['results']))

    def test_known_issues(self):
        data = self.hit('/api/knownissues/')
        self.assertEqual(1, len(data['results']))
