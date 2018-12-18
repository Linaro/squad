import datetime
import json
from mock import patch
from test.api import APIClient
from django.test import TestCase
from django.utils import timezone
from squad.core import models
from squad.core.tasks import UpdateProjectStatus
from squad.ci import models as ci_models
from rest_framework.reverse import reverse
from test.performance import count_queries


class RestApiTest(TestCase):

    def setUp(self):
        self.group = models.Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        t = timezone.make_aware(datetime.datetime(2018, 10, 1, 1, 0, 0))
        self.build = self.project.builds.create(version='1', datetime=t)
        t2 = timezone.make_aware(datetime.datetime(2018, 10, 2, 1, 0, 0))
        self.build2 = self.project.builds.create(version='2', datetime=t2)
        t3 = timezone.make_aware(datetime.datetime(2018, 10, 3, 1, 0, 0))
        self.build3 = self.project.builds.create(version='3', datetime=t3)
        self.environment = self.project.environments.create(slug='myenv')
        self.environment_a = self.project.environments.create(slug='env-a')
        self.testrun = self.build.test_runs.create(environment=self.environment, build=self.build)
        self.testrun2 = self.build2.test_runs.create(environment=self.environment, build=self.build2)
        self.testrun3 = self.build3.test_runs.create(environment=self.environment, build=self.build3)
        self.testrun_a = self.build.test_runs.create(environment=self.environment_a, build=self.build)
        self.testrun2_a = self.build2.test_runs.create(environment=self.environment_a, build=self.build2)
        self.testrun3_a = self.build3.test_runs.create(environment=self.environment_a, build=self.build3)
        self.backend = ci_models.Backend.objects.create(name='foobar')
        self.patchsource = models.PatchSource.objects.create(name='baz_source', username='u', url='http://example.com', token='secret')
        self.knownissue = models.KnownIssue.objects.create(title='knownissue_foo', test_name='test/bar', active=True)
        self.knownissue.environments.add(self.environment)

        self.testjob = ci_models.TestJob.objects.create(
            definition="foo: bar",
            backend=self.backend,
            target=self.project,
            target_build=self.build,
            environment='myenv',
            testrun=self.testrun
        )
        self.testjob2 = ci_models.TestJob.objects.create(
            definition="foo: bar",
            backend=self.backend,
            target=self.project,
            target_build=self.build2,
            environment='myenv',
            testrun=self.testrun2
        )
        self.testjob3 = ci_models.TestJob.objects.create(
            definition="foo: bar",
            backend=self.backend,
            target=self.project,
            target_build=self.build3,
            environment='myenv',
            testrun=self.testrun3
        )

        testrun_sets = [
            [self.testrun, self.testrun2, self.testrun3],  # environment: myenv
            [self.testrun_a, self.testrun2_a, self.testrun3_a],  # environment: env-a
        ]
        tests = {
            'foo/test1': ['pass', 'fail', 'pass'],  # fix
            'foo/test2': ['pass', 'pass', 'fail'],  # regression
            'foo/test3': ['pass', 'pass', 'pass'],
            'foo/test4': ['pass', 'pass', 'pass'],
            'foo/test5': ['pass', 'pass', 'pass'],
            'foo/test6': ['pass', 'pass', 'pass'],
            'foo/test7': ['pass', 'pass', 'pass'],
            'foo/test8': ['pass', 'pass', 'pass'],
            'foo/test9': ['pass', 'pass', 'pass'],
            'bar/test1': ['pass', 'pass', 'pass'],
            'bar/test2': ['fail', 'fail', 'fail'],
            'bar/test3': ['fail', 'fail', 'fail'],
            'bar/test4': ['fail', 'fail', 'fail'],
            'bar/test5': ['fail', 'fail', 'fail'],
            'bar/test6': ['fail', 'fail', 'fail'],
            'bar/test7': ['fail', 'fail', 'fail'],
            'bar/test8': ['fail', 'fail', 'fail'],
            'bar/test9': ['fail', 'fail', 'fail'],
        }
        for test_name in tests.keys():
            for testruns in testrun_sets:
                for i in [0, 1, 2]:
                    testrun = testruns[i]
                    result = tests[test_name][i]
                    s, t = test_name.split('/')
                    r = {'pass': True, 'fail': False}[result]
                    suite, _ = self.project.suites.get_or_create(slug=s)
                    testrun.tests.create(suite=suite, name=t, result=r)

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
        with count_queries('url:' + url):
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
        self.hit('/api/builds/%d/status/' % self.build.id)

    def test_builds_email_missing_status(self):
        # this should not happen normally, but let's test it anyway
        self.build3.status.delete()
        response = self.client.get('/api/builds/%d/email/' % self.build3.id)
        self.assertEqual(404, response.status_code)

    def test_builds_email(self):
        # update ProjectStatus
        self.build2.test_jobs.all().delete()
        self.build3.test_jobs.all().delete()
        UpdateProjectStatus()(self.testrun2)
        UpdateProjectStatus()(self.testrun3)
        response = self.hit('/api/builds/%d/email/' % self.build3.id)
        self.assertIn('foo/test2', response)  # sanity check
        self.assertIn('Regressions (compared to build 2)', response)  # make sure proper baseline is used

    def test_builds_email_custom_template(self):
        # update ProjectStatus
        UpdateProjectStatus()(self.testrun2)
        UpdateProjectStatus()(self.testrun3)
        response = self.client.get('/api/builds/%d/email/?template=%s' % (self.build3.id, self.validemailtemplate.pk))
        self.assertEqual(200, response.status_code)
        self.assertEqual("text/plain", response['Content-Type'])

    def test_builds_email_custom_invalid_template(self):
        # update ProjectStatus
        UpdateProjectStatus()(self.testrun2)
        UpdateProjectStatus()(self.testrun3)
        response = self.client.get('/api/builds/%d/email/?template=%s' % (self.build3.id, self.invalidemailtemplate.pk))
        self.assertEqual(400, response.status_code)

    def test_builds_email_custom_baseline(self):
        UpdateProjectStatus()(self.testrun)
        UpdateProjectStatus()(self.testrun3)
        response = self.client.get('/api/builds/%d/email/?baseline=%s&output=text/plain' % (self.build3.id, self.build.id))
        self.assertContains(response, "Regressions (compared to build 1)")

    def test_builds_email_custom_baseline_html(self):
        UpdateProjectStatus()(self.testrun)
        UpdateProjectStatus()(self.testrun3)
        response = self.client.get('/api/builds/%d/email/?baseline=%s&output=text/html' % (self.build3.id, self.build.id))
        self.assertContains(response, "Regressions (compared to build 1)", html=True)

    def test_builds_email_custom_baseline_missing_status(self):
        UpdateProjectStatus()(self.testrun)
        self.build2.status.delete()
        response = self.client.get('/api/builds/%d/email/?baseline=%s' % (self.build.id, self.build2.id))
        self.assertEqual(400, response.status_code)

    def test_builds_email_custom_invalid_baseline(self):
        UpdateProjectStatus()(self.testrun)
        response = self.client.get('/api/builds/%d/email/?baseline=999' % (self.build.id))
        self.assertEqual(400, response.status_code)

    @patch('squad.core.tasks.prepare_report.delay')
    def test_build_report(self, prepare_report_mock):
        response = self.client.get('/api/builds/%d/report/' % self.build3.id)
        self.assertEqual(202, response.status_code)
        report_object = self.build3.delayed_reports.last()
        self.assertTrue(response.json()['url'].endswith(reverse('delayedreport-detail', args=[report_object.pk])))
        self.assertIsNotNone(report_object)
        self.assertIsNone(report_object.status_code)
        self.assertEqual(report_object.baseline, None)  # default baseline is used
        prepare_report_mock.assert_called()

    @patch('squad.core.tasks.prepare_report.delay')
    def test_build_report_baseline(self, prepare_report_mock):
        response = self.client.get('/api/builds/%d/report/?baseline=%s' % (self.build3.id, self.build.id))
        self.assertEqual(202, response.status_code)
        report_object = self.build3.delayed_reports.last()
        self.assertTrue(response.json()['url'].endswith(reverse('delayedreport-detail', args=[report_object.pk])))
        report_json = self.client.get(response.json()['url'])
        self.assertTrue(report_json.json()['baseline'].endswith(reverse('build-status', args=[self.build.id])))
        self.assertIsNotNone(report_object)
        self.assertIsNone(report_object.status_code)
        self.assertEqual(report_object.baseline, self.build.status)
        prepare_report_mock.assert_called()

    @patch('squad.core.tasks.prepare_report.delay')
    def test_build_report_baseline2(self, prepare_report_mock):
        response = self.client.get('/api/builds/%d/report/?baseline=%s' % (self.build3.id, self.build2.id))
        self.assertEqual(202, response.status_code)
        report_object = self.build3.delayed_reports.last()
        self.assertTrue(response.json()['url'].endswith(reverse('delayedreport-detail', args=[report_object.pk])))
        report_object = self.client.get(response.json()['url'])
        self.assertTrue(report_object.json()['baseline'].endswith(reverse('build-status', args=[self.build2.id])))
        prepare_report_mock.assert_called()

    @patch('squad.core.tasks.prepare_report.delay')
    def test_build_report_retry(self, prepare_report_mock):
        response = self.client.get('/api/builds/%d/report/' % self.build3.id)
        self.assertEqual(202, response.status_code)
        self.client.get('/api/builds/%d/report/' % self.build3.id)
        report_object = self.build3.delayed_reports.last()
        self.assertTrue(response.json()['url'].endswith(reverse('delayedreport-detail', args=[report_object.pk])))
        self.assertIsNotNone(report_object)
        self.assertIsNone(report_object.status_code)
        prepare_report_mock.assert_called_once()
        prepare_report_mock.reset_mock()
        response2 = self.client.get('/api/builds/%d/report/' % self.build3.id)
        self.assertEqual(response.json(), response2.json())
        prepare_report_mock.assert_not_called()

    @patch('squad.core.tasks.prepare_report.delay')
    def test_build_report_retry_force(self, prepare_report_mock):
        response = self.client.get('/api/builds/%d/report/' % self.build3.id)
        self.assertEqual(202, response.status_code)
        self.client.get('/api/builds/%d/report/' % self.build3.id)
        report_object = self.build3.delayed_reports.last()
        self.assertTrue(response.json()['url'].endswith(reverse('delayedreport-detail', args=[report_object.pk])))
        self.assertIsNotNone(report_object)
        self.assertIsNone(report_object.status_code)
        prepare_report_mock.assert_called_once()
        prepare_report_mock.reset_mock()
        response2 = self.client.get('/api/builds/%d/report/?force=true' % self.build3.id)
        self.assertEqual(response.json(), response2.json())
        prepare_report_mock.assert_called_once()

    def test_build_testruns(self):
        data = self.hit('/api/builds/%d/testruns/' % self.build.id)
        self.assertEqual(2, len(data['results']))

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
        self.assertEqual(['env-a', 'myenv'], sorted([item['slug'] for item in data['results']]))

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
