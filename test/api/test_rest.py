import datetime
import json
from test.mock import patch
from django.contrib.admin.models import LogEntry, ADDITION, DELETION, CHANGE
from django.utils import timezone
from squad.core import models
from squad.core.tasks import UpdateProjectStatus, ReceiveTestRun, RecordTestRunStatus, ParseTestRunData
from squad.ci import models as ci_models
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from test.performance import count_queries


class RestApiTest(APITestCase):

    def setUp(self):
        self.group = models.Group.objects.create(slug='mygroup')
        self.group2 = models.Group.objects.create(slug='mygroup2')
        self.project = self.group.projects.create(slug='myproject')
        self.project2 = self.group.projects.create(slug='myproject2')
        self.project3 = self.group2.projects.create(slug='myproject2')
        t = timezone.make_aware(datetime.datetime(2018, 10, 1, 1, 0, 0))
        self.build = self.project.builds.create(version='1', datetime=t)
        t2 = timezone.make_aware(datetime.datetime(2018, 10, 2, 1, 0, 0))
        self.build2 = self.project.builds.create(version='2', datetime=t2)
        t3 = timezone.make_aware(datetime.datetime(2018, 10, 3, 1, 0, 0))
        self.build3 = self.project.builds.create(version='3', datetime=t3)
        t4 = timezone.make_aware(datetime.datetime(2018, 10, 4, 1, 0, 0))
        self.build4 = self.project.builds.create(version='v4', datetime=t4)
        t5 = timezone.make_aware(datetime.datetime(2018, 10, 5, 1, 0, 0))
        self.build5 = self.project.builds.create(version='5', datetime=t5)
        t6 = timezone.make_aware(datetime.datetime(2018, 10, 6, 1, 0, 0))
        self.build6 = self.project.builds.create(version='v6', datetime=t6)
        self.build7 = self.project3.builds.create(version='1', datetime=t2)
        self.environment = self.project.environments.create(slug='myenv', expected_test_runs=1)
        self.environment2 = self.project3.environments.create(slug='myenv', expected_test_runs=1)
        self.environment_a = self.project.environments.create(slug='env-a')
        self.environment_a2 = self.project3.environments.create(slug='env-a')
        self.testrun = self.build.test_runs.create(environment=self.environment, metadata_file='{"key1": "val1"}')
        self.testrun2 = self.build2.test_runs.create(environment=self.environment)
        self.testrun3 = self.build3.test_runs.create(environment=self.environment)
        self.testrun4 = self.build4.test_runs.create(environment=self.environment, completed=True)
        self.testrun6 = self.build6.test_runs.create(environment=self.environment, completed=True)
        self.testrun_a = self.build.test_runs.create(environment=self.environment_a, metadata_file='{"key2": "val2"}')
        self.testrun2_a = self.build2.test_runs.create(environment=self.environment_a, build=self.build2)
        self.testrun3_a = self.build3.test_runs.create(environment=self.environment_a, build=self.build3)
        self.testrun7 = self.build7.test_runs.create(environment=self.environment2)
        self.testrun7_a = self.build7.test_runs.create(environment=self.environment_a2)
        self.backend = ci_models.Backend.objects.create(name='foobar')
        self.fake_backend = ci_models.Backend.objects.create(name='foobarfake', implementation_type='fake')
        self.patchsource = models.PatchSource.objects.create(name='baz_source', username='u', url='http://example.com', token='secret')
        self.knownissue = models.KnownIssue.objects.create(title='knownissue_foo', test_name='test/bar', active=True)
        self.knownissue.environments.add(self.environment)
        self.knownissue2 = models.KnownIssue.objects.create(title='knownissue_bar', test_name='test/foo', active=True)
        self.knownissue2.environments.add(self.environment_a)
        self.testuser = models.User.objects.create(username='test_user', email="test@example.com", is_superuser=False)

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
            testrun=self.testrun2,
        )
        self.testjob3 = ci_models.TestJob.objects.create(
            definition="foo: bar",
            backend=self.backend,
            target=self.project,
            target_build=self.build3,
            environment='myenv',
            testrun=self.testrun3
        )
        self.testjob5 = ci_models.TestJob.objects.create(
            definition="foo: bar",
            backend=self.fake_backend,
            target=self.project,
            target_build=self.build5,
            environment='myenv',
            job_id='1234',
            submitted=True
        )
        self.testjob6 = ci_models.TestJob.objects.create(
            definition="foo: bar",
            backend=self.fake_backend,
            target=self.project,
            target_build=self.build5,
            environment='myenv',
            job_id='1235',
            submitted=True,
            fetched=True,
            can_resubmit=True,
            parent_job=self.testjob5,
        )

        testrun_sets = [
            [self.testrun, self.testrun2, self.testrun3, self.testrun7],  # environment: myenv
            [self.testrun_a, self.testrun2_a, self.testrun3_a, self.testrun7_a],  # environment: env-a
        ]
        tests = {
            'foo/test1': ['pass', 'fail', 'pass', 'pass'],  # fix
            'foo/test2': ['pass', 'pass', 'fail', 'fail'],  # regression
            'foo/test3': ['pass', 'pass', 'pass', 'pass'],
            'foo/test4': ['pass', 'pass', 'pass', 'pass'],
            'foo/test5': ['pass', 'pass', 'pass', 'pass'],
            'foo/test6': ['pass', 'pass', 'pass', 'pass'],
            'foo/test7': ['pass', 'pass', 'pass', 'pass'],
            'foo/test8': ['pass', 'pass', 'pass', 'pass'],
            'foo/test9': ['pass', 'pass', 'pass', 'pass'],
            'bar/test1': ['pass', 'pass', 'pass', 'pass'],
            'bar/test2': ['fail', 'fail', 'fail', 'pass'],
            'bar/test3': ['fail', 'fail', 'fail', 'fail'],
            'bar/test4': ['fail', 'fail', 'fail', 'fail'],
            'bar/test5': ['fail', 'fail', 'fail', 'fail'],
            'bar/test6': ['fail', 'fail', 'fail', 'fail'],
            'bar/test7': ['fail', 'fail', 'fail', 'fail'],
            'bar/test8': ['fail', 'fail', 'fail', 'fail'],
            'bar/test9': ['fail', 'fail', 'fail', 'fail'],
        }
        for test_name in tests.keys():
            for testruns in testrun_sets:
                for i, testrun in enumerate(testruns):
                    result = tests[test_name][i]
                    s, t = test_name.split('/')
                    r = {'pass': True, 'fail': False}[result]
                    suite, _ = testrun.build.project.suites.get_or_create(slug=s)
                    metadata, _ = models.SuiteMetadata.objects.get_or_create(suite=s, name=t, kind='test')
                    testrun.tests.create(suite=suite, result=r, metadata=metadata, build=testrun.build, environment=testrun.environment)

        metric_suite = 'mymetricsuite'
        suite, _ = self.project.suites.get_or_create(slug=metric_suite)
        metadata, _ = models.SuiteMetadata.objects.get_or_create(suite=metric_suite, name='mymetric', kind='metric')
        self.testrun.metrics.create(suite=suite, result=1, metadata=metadata, build=self.build, environment=self.environment)

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

    def post(self, url, data):
        user, _ = models.User.objects.get_or_create(username='u', is_superuser=True)
        if not self.group.members.filter(pk=user.pk).exists():
            self.group.add_admin(user)
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        response = self.client.post(url, data)
        return response

    def get(self, url):
        user, _ = models.User.objects.get_or_create(username='u', is_superuser=True)
        if not self.group.members.filter(pk=user.pk).exists():
            self.group.add_admin(user)
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        response = self.client.get(url)
        return response

    def receive(self, datestr, env, metrics={}, tests={}):
        receive = ReceiveTestRun(self.project)
        testrun, _ = receive(
            version=datestr,
            environment_slug=env,
            metadata_file=json.dumps(
                {"datetime": datestr + "T00:00:00+00:00", "job_id": "1"}
            ),
            metrics_file=json.dumps(metrics),
            tests_file=json.dumps(tests),
        )
        return testrun

    def test_root(self):
        self.hit('/api/')

    def test_projects(self):
        data = self.hit('/api/projects/')
        self.assertEqual(3, len(data['results']))

    def test_project_basic_settings(self):
        data = self.hit('/api/projects/%d/basic_settings/' % self.project.id)
        self.assertTrue("build_confidence_count" in data)
        self.assertTrue("build_confidence_threshold" in data)

    def test_project_builds(self):
        data = self.hit('/api/projects/%d/builds/' % self.project.id)
        self.assertEqual(6, len(data['results']))

    def test_project_test_results(self):
        response = self.client.get('/api/projects/%d/test_results/' % self.project.id)
        self.assertEqual(400, response.status_code)

        data = self.hit('/api/projects/%d/test_results/?test_name=foo/test1' % self.project.id)
        self.assertTrue(len(data) > 0)

    def test_create_project_with_enabled_plugin_list_1_element(self):
        response = self.post(
            '/api/projects/',
            {
                'group': "http://testserver/api/groups/%d/" % self.group.id,
                'slug': 'newproject',
                'enabled_plugins_list': ['foo'],
            }
        )
        self.assertEqual(201, response.status_code)
        project = self.hit('/api/projects/?slug=newproject')['results'][0]
        self.assertEqual(['foo'], project['enabled_plugins_list'])

    def test_create_project_with_enabled_plugin_list_2_elements(self):
        response = self.post(
            '/api/projects/',
            {
                'group': "http://testserver/api/groups/%d/" % self.group.id,
                'slug': 'newproject',
                'enabled_plugins_list': ['foo', 'bar'],
            }
        )
        self.assertEqual(201, response.status_code)
        project = self.hit('/api/projects/?slug=newproject')['results'][0]
        self.assertEqual(['foo', 'bar'], project['enabled_plugins_list'])

    def test_create_project_with_non_admin_account(self):
        user, _ = models.User.objects.get_or_create(username='u')
        self.group.add_user(user)
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        response = self.client.post(
            '/api/projects/',
            {
                'group': "http://testserver/api/groups/%d/" % self.group.id,
                'slug': 'newproject',
                'enabled_plugins_list': ['foo', 'bar'],
            }
        )
        self.assertEqual(201, response.status_code)
        project = self.client.get('/api/projects/?slug=newproject').json()['results'][0]
        self.assertEqual(['foo', 'bar'], project['enabled_plugins_list'])

    def test_project_subscribe_unsubscribe_email(self):
        email_addr = "foo@bar.com"
        response = self.post(
            '/api/projects/%s/subscribe/' % self.project.pk,
            {
                'email': email_addr
            }
        )
        self.assertEqual(201, response.status_code)
        subscription_queryset = self.project.subscriptions.filter(email=email_addr)
        self.assertTrue(subscription_queryset.exists())
        user = models.User.objects.get(username='u')
        subscription = subscription_queryset.last().pk
        logentry_queryset = LogEntry.objects.filter(
            user_id=user.pk,
            object_id=subscription
        )
        self.assertEqual(
            1,
            logentry_queryset.count()
        )
        self.assertEqual(
            ADDITION,
            logentry_queryset.first().action_flag
        )

        response1 = self.post(
            '/api/projects/%s/unsubscribe/' % self.project.pk,
            {
                'email': email_addr
            }
        )
        self.assertEqual(200, response1.status_code)
        self.assertFalse(self.project.subscriptions.filter(email=email_addr).exists())
        self.assertEqual(
            2,
            logentry_queryset.count()
        )
        self.assertEqual(
            DELETION,
            logentry_queryset.first().action_flag
        )

    def test_project_unsubscribe_email_different_project(self):
        email_addr = "foo@bar.com"
        response = self.post(
            '/api/projects/%s/subscribe/' % self.project.pk,
            {
                'email': email_addr
            }
        )
        self.assertEqual(201, response.status_code)
        response1 = self.post(
            '/api/projects/%s/subscribe/' % self.project2.pk,
            {
                'email': email_addr
            }
        )
        self.assertEqual(201, response1.status_code)

        self.assertTrue(self.project.subscriptions.filter(email=email_addr).exists())
        self.assertTrue(self.project2.subscriptions.filter(email=email_addr).exists())
        response2 = self.post(
            '/api/projects/%s/unsubscribe/' % self.project2.pk,
            {
                'email': email_addr
            }
        )
        self.assertEqual(200, response2.status_code)
        self.assertTrue(self.project.subscriptions.filter(email=email_addr).exists())
        self.assertFalse(self.project2.subscriptions.filter(email=email_addr).exists())

    def test_project_subscribe_invalid_email(self):
        email_addr = "foo@bar@com"
        response = self.post(
            '/api/projects/%s/subscribe/' % self.project.pk,
            {
                'email': email_addr
            }
        )
        self.assertEqual(400, response.status_code)
        self.assertFalse(self.project.subscriptions.filter(email=email_addr).exists())

    def test_project_unsubscribe_invalid_email(self):
        email_addr = "foo@bar@com"
        response = self.post(
            '/api/projects/%s/unsubscribe/' % self.project.pk,
            {
                'email': email_addr
            }
        )
        self.assertEqual(400, response.status_code)

    def test_project_subscribe_unsubscribe_user(self):
        response = self.post(
            '/api/projects/%s/subscribe/' % self.project.pk,
            {
                'email': self.testuser.email
            }
        )
        self.assertEqual(201, response.status_code)
        self.assertTrue(self.project.subscriptions.filter(user=self.testuser).exists())
        response1 = self.post(
            '/api/projects/%s/unsubscribe/' % self.project.pk,
            {
                'email': self.testuser.email
            }
        )
        self.assertEqual(200, response1.status_code)
        self.assertFalse(self.project.subscriptions.filter(email=self.testuser.email).exists())

    def test_project_subscribe_missing_email(self):
        email_addr = "foo@bar.com"
        response = self.post(
            '/api/projects/%s/subscribe/' % self.project.pk,
            {
                'email_foo': email_addr
            }
        )
        self.assertEqual(400, response.status_code)

    def test_project_unsubscribe_missing_email(self):
        email_addr = "foo@bar.com"
        response = self.post(
            '/api/projects/%s/unsubscribe/' % self.project.pk,
            {
                'email_foo': email_addr
            }
        )
        self.assertEqual(400, response.status_code)

    def test_builds(self):
        data = self.hit('/api/builds/')
        self.assertEqual(7, len(data['results']))

    def test_builds_id_filter(self):
        last = self.project.builds.last()
        data = self.hit(f'/api/builds/?id__lt={last.id}')
        self.assertEqual(5, len(data['results']))

    def test_builds_status(self):
        self.build2.test_jobs.all().delete()
        self.build3.test_jobs.all().delete()
        UpdateProjectStatus()(self.testrun2)
        UpdateProjectStatus()(self.testrun3)

        data = self.hit('/api/builds/%d/status/' % self.build3.id)
        self.assertIn('foo/test2', data['regressions'])
        self.assertIn('foo/test1', data['fixes'])
        self.assertNotIn('myenv', data['details'])

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
        logentry_queryset = LogEntry.objects.filter(
            object_id=report_object.pk
        )
        self.assertEqual(
            0,  # do not create LogEntry for anonymous users
            logentry_queryset.count()
        )

    def test_build_callbacks(self):
        response = self.get('/api/builds/%d/callbacks/' % self.build.id)
        self.assertEqual(202, response.status_code)
        self.assertEqual(0, len(response.json()['results']))

        callback_url = 'http://callback.url'
        response = self.post('/api/builds/%d/callbacks/' % self.build.id, {'callback_url': callback_url})
        self.assertEqual(202, response.status_code)
        self.assertEqual('OK', response.json()['message'])

        response = self.get('/api/builds/%d/callbacks/' % self.build.id)
        self.assertEqual(202, response.status_code)
        self.assertEqual(1, len(response.json()['results']))

        response = self.post('/api/builds/%d/callbacks/' % self.build.id, {'callback_url': 'invalid-callback.url'})
        self.assertEqual(400, response.status_code)
        self.assertEqual('Enter a valid URL.', response.json()['message'])

        response = self.post('/api/builds/%d/callbacks/' % self.build.id, {'callback_url': callback_url})
        self.assertEqual(400, response.status_code)
        self.assertEqual('Callback with this Object reference type, Object reference id, Url and Event already exists.', response.json()['message'])

    def test_build_callback_headers(self):
        headers = '{"Authorization": "token 123456"}'
        self.project.project_settings = '{"CALLBACK_HEADERS": %s}' % headers
        self.project.save()

        callback_url = 'http://callback.url'
        response = self.post('/api/builds/%d/callbacks/' % self.build.id, {'callback_url': callback_url})
        self.assertEqual(202, response.status_code)
        self.assertEqual('OK', response.json()['message'])
        self.assertEqual(1, self.build.callbacks.filter(url=callback_url, headers=headers).count())

        # Check that headers in project settings gets overwritten if it comes from the user
        user_headers = '{"Authorization": "token 654321"}'
        callback_url += '/with-headers'
        response = self.post('/api/builds/%d/callbacks/' % self.build.id, {'callback_url': callback_url, 'callback_headers': user_headers})
        self.assertEqual(202, response.status_code)
        self.assertEqual('OK', response.json()['message'])
        self.assertEqual(1, self.build.callbacks.filter(url=callback_url, headers=user_headers).count())

    @patch('squad.core.tasks.prepare_report.delay')
    def test_zz_build_report_logentry(self, prepare_report_mock):
        response = self.get('/api/builds/%d/report/' % self.build3.id)
        self.assertEqual(202, response.status_code)
        report_object = self.build3.delayed_reports.last()
        self.assertTrue(response.json()['url'].endswith(reverse('delayedreport-detail', args=[report_object.pk])))
        self.assertIsNotNone(report_object)
        self.assertIsNone(report_object.status_code)
        self.assertEqual(report_object.baseline, None)  # default baseline is used
        prepare_report_mock.assert_called()
        user = models.User.objects.get(username='u')
        logentry_queryset = LogEntry.objects.filter(
            user_id=user.pk,
            object_id=report_object.pk
        )
        self.assertEqual(
            1,
            logentry_queryset.count()
        )
        self.assertEqual(
            ADDITION,
            logentry_queryset.first().action_flag
        )

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
    def test_build_report_baseline_cache(self, prepare_report_mock):
        response = self.client.get('/api/builds/%d/report/?baseline=%s' % (self.build3.id, self.build.id))
        self.assertEqual(202, response.status_code)
        report_object = self.build3.delayed_reports.last()
        report_url = response.json()['url']
        self.assertTrue(report_url.endswith(reverse('delayedreport-detail', args=[report_object.pk])))
        report_json = self.client.get(report_url)
        self.assertTrue(report_json.json()['baseline'].endswith(reverse('build-status', args=[self.build.id])))
        self.assertIsNotNone(report_object)
        self.assertIsNone(report_object.status_code)
        self.assertEqual(report_object.baseline, self.build.status)
        prepare_report_mock.assert_called()
        response2 = self.client.get('/api/builds/%d/report/?baseline=%s' % (self.build3.id, self.build.id))
        self.assertEqual(report_url, response2.json()['url'])

    @patch('squad.core.tasks.prepare_report.delay')
    def test_build_report_invalid_baseline(self, prepare_report_mock):
        response = self.client.get('/api/builds/%d/report/?baseline=123456789' % (self.build3.id))
        self.assertEqual(202, response.status_code)
        report_object = self.build3.delayed_reports.last()
        self.assertTrue(response.json()['url'].endswith(reverse('delayedreport-detail', args=[report_object.pk])))
        report_json = self.client.get(response.json()['url'])
        self.assertIsNone(report_json.json()['baseline'])
        self.assertIsNotNone(report_object)
        self.assertIsNotNone(report_object.status_code)
        self.assertEqual(report_object.status_code, 400)
        prepare_report_mock.assert_not_called()

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
        self.assertNotEqual(response.json()['url'], response2.json()['url'])
        prepare_report_mock.assert_called_once()

    @patch('squad.core.tasks.prepare_report.delay')
    def test_build_report_retry_force_logentry(self, prepare_report_mock):
        response = self.get('/api/builds/%d/report/' % self.build3.id)
        self.assertEqual(202, response.status_code)
        user = models.User.objects.get(username='u')
        report_object = self.build3.delayed_reports.last()
        logentry_queryset = LogEntry.objects.filter(
            user_id=user.pk,
            object_id=report_object.pk
        )
        self.assertEqual(
            1,
            logentry_queryset.count()
        )
        self.assertEqual(
            ADDITION,
            logentry_queryset.first().action_flag
        )
        self.client.get('/api/builds/%d/report/' % self.build3.id)
        self.assertEqual(
            2,
            logentry_queryset.count()
        )
        self.assertEqual(
            CHANGE,
            logentry_queryset.first().action_flag
        )
        self.assertTrue(response.json()['url'].endswith(reverse('delayedreport-detail', args=[report_object.pk])))
        self.assertIsNotNone(report_object)
        self.assertIsNone(report_object.status_code)
        prepare_report_mock.assert_called_once()
        prepare_report_mock.reset_mock()
        response2 = self.get('/api/builds/%d/report/?force=true' % self.build3.id)
        self.assertNotEqual(response.json()['url'], response2.json()['url'])
        prepare_report_mock.assert_called_once()
        report_object2 = self.build3.delayed_reports.last()
        logentry_queryset2 = LogEntry.objects.filter(
            user_id=user.pk,
            object_id=report_object2.pk
        )
        self.assertEqual(
            1,
            logentry_queryset2.count()
        )
        self.assertEqual(
            ADDITION,
            logentry_queryset2.first().action_flag
        )

    def test_build_testruns(self):
        data = self.hit('/api/builds/%d/testruns/' % self.build.id)
        self.assertEqual(2, len(data['results']))

    def test_build_testjobs(self):
        data = self.hit('/api/builds/%d/testjobs/' % self.build.id)
        self.assertEqual(1, len(data['results']))

    def test_build_testjobs_summary(self):
        data = self.hit('/api/builds/%d/testjobs_summary/' % self.build.id)
        self.assertEqual(1, len(data['results']))
        self.assertEqual({'null': 1}, data['results'])

    def test_build_testjobs_summary_per_environment(self):
        data = self.hit('/api/builds/%d/testjobs_summary/?per_environment=1' % self.build.id)
        self.assertEqual(1, len(data['results']))
        self.assertEqual({'myenv': {'null': 1}}, data['results'])

    def test_build_tests(self):
        data = self.hit('/api/builds/%d/tests/' % self.build.id)
        self.assertEqual(36, len(data['results']))

    def test_build_tests_per_environment(self):
        data = self.hit('/api/builds/%d/tests/?environment__slug=myenv' % self.build.id)
        self.assertEqual(18, len(data['results']))

    def test_build_tests_per_environment_not_found(self):
        data = self.hit('/api/builds/%d/tests/?environment__slug=mycrazynonexistenenv' % self.build.id)
        self.assertEqual(0, len(data['results']))

    def test_build_tests_per_suite(self):
        data = self.hit('/api/builds/%d/tests/?suite__slug=foo' % self.build.id)
        self.assertEqual(18, len(data['results']))

    def test_build_tests_per_suite_not_found(self):
        data = self.hit('/api/builds/%d/tests/?suite__slug=fooooooodoesreallyexist' % self.build.id)
        self.assertEqual(0, len(data['results']))

    def test_build_tests_per_suite_and_environment(self):
        data = self.hit('/api/builds/%d/tests/?environment__slug=myenv&suite__slug=foo' % self.build.id)
        self.assertEqual(9, len(data['results']))

        data = self.hit('/api/builds/%d/tests/?environment__slug=mycraaaaazyenv&suite__slug=foo' % self.build.id)
        self.assertEqual(0, len(data['results']))

        data = self.hit('/api/builds/%d/tests/?environment__slug=myenv&suite__slug=foooooooosuitedoestexist' % self.build.id)
        self.assertEqual(0, len(data['results']))

    def test_build_failures_with_confidence(self):
        data = self.hit('/api/builds/%d/failures_with_confidence/' % self.build3.id)

        self.assertEqual(data['count'], 18)
        self.assertIsNone(data['next'])
        self.assertIsNone(data['previous'])
        self.assertEqual(len(data['results']), 18)

        failure = data['results'].pop(0)
        self.assertEqual(failure['name'], 'bar/test2')
        self.assertEqual(failure['result'], False)
        self.assertEqual(failure['status'], 'fail')
        self.assertEqual(failure['confidence'], {'count': 2, 'passes': 0, 'score': 0.0})

    def test_build_failures_with_confidence_with_first_build(self):
        """
        The first build will not have any history, so the confidence scores for those failures should all be zero
        """
        data = self.hit('/api/builds/%d/failures_with_confidence/' % self.build.id)

        for f in data['results']:
            self.assertEqual(f['confidence'], {'count': 0, 'passes': 0, 'score': 0})

    def test_build_failures_with_confidence_with_pagination(self):
        data = self.hit('/api/builds/%d/failures_with_confidence/?limit=2' % self.build3.id)

        self.assertEqual(data['count'], 18)
        self.assertIsNotNone(data['next'])
        self.assertIsNone(data['previous'])
        self.assertEqual(len(data['results']), 2)

        failure = data['results'][0]
        self.assertEqual(failure['name'], 'bar/test2')
        self.assertEqual(failure['result'], False)
        self.assertEqual(failure['status'], 'fail')
        self.assertEqual(failure['confidence'], {'count': 2, 'passes': 0, 'score': 0.0})

        failure = data['results'][1]
        self.assertEqual(failure['name'], 'bar/test2')
        self.assertEqual(failure['result'], False)
        self.assertEqual(failure['status'], 'fail')
        self.assertEqual(failure['confidence'], {'count': 2, 'passes': 0, 'score': 0.0})

    def test_build_metrics(self):
        data = self.hit('/api/builds/%d/metrics/' % self.build.id)
        self.assertEqual(1, len(data['results']))

    def test_build_metadata(self):
        data = self.hit('/api/builds/%d/metadata/' % self.build.id)
        self.assertEqual('val1', data['key1'])
        self.assertEqual('val2', data['key2'])

    def test_build_metadata_by_testrun(self):
        data = self.hit('/api/builds/%d/metadata_by_testrun/' % self.build.id)
        self.assertEqual({"key1": "val1"}, data[str(self.testrun.id)])
        self.assertEqual({"key2": "val2"}, data[str(self.testrun_a.id)])

    def test_build_filter(self):
        created_at = str(self.build3.created_at.isoformat()).replace('+00:00', 'Z')
        data = self.hit('/api/builds/?created_at=%s' % created_at)
        self.assertEqual(1, len(data['results']))

    def test_build_filter_by_project(self):
        project_full_name = self.build3.project.full_name
        data = self.hit('/api/builds/?project__full_name=%s' % project_full_name)
        self.assertEqual(6, len(data['results']))

    def test_build_minimum_fields(self):
        data = self.hit('/api/builds/%d/?fields=version' % self.build.id)

        should_not_exist = {'url', 'id', 'testruns', 'testjobs', 'status', 'metadata', 'finished', 'created_at', 'datetime', 'patch_id', 'keep_data', 'project', 'patch_source', 'patch_baseline'}

        fields = set(data.keys())
        self.assertEqual(set(), should_not_exist & fields)
        self.assertTrue('version' in fields)
        self.assertEqual(1, len(fields))

    def test_build_cancel(self):
        testjob = self.build.test_jobs.first()
        testjob.submitted = True
        testjob.save()
        self.assertEqual(self.build.test_jobs.filter(job_status='Canceled').count(), 0)
        data = self.post('/api/builds/%d/cancel/' % self.build.id, {})
        self.assertEqual(data.status_code, 200)
        self.assertEqual(data.json()['count'], 1)
        self.assertEqual(self.build.test_jobs.filter(job_status='Canceled').count(), 1)

    def test_build_compare_400_on_unfinished_build(self):
        response = self.get('/api/builds/%d/compare/?target=%d' % (self.build.id, self.build2.id))
        self.assertEqual(400, response.status_code)
        self.assertEqual('["Cannot report regressions/fixes on non-finished builds"]', response.content.decode('utf-8'))

    def test_build_compare_against_same_project(self):
        url = '/api/builds/%d/compare/?target=%d&force=true' % (self.build.id, self.build2.id)
        data = self.hit(url)
        expected = {
            "regressions":
            {
                "myenv":
                {
                    "foo": ["test1"]
                },
                "env-a":
                {
                    "foo": ["test1"]
                }
            },
            "fixes": {}
        }
        self.assertEqual(expected, data)

    def test_build_compare_against_different_project(self):
        url = '/api/builds/%d/compare/?target=%d&force=true' % (self.build.id, self.build7.id)
        data = self.hit(url)
        expected = {
            'regressions':
            {
                'myenv': {
                    'foo': ['test2']
                },
                'env-a':
                {
                    'foo': ['test2']
                }
            },
            'fixes': {
                'myenv': {
                    'bar': ['test2']
                },
                'env-a': {
                    'bar': ['test2']
                }
            }
        }
        self.assertEqual(expected, data)

    def test_testjob(self):
        data = self.hit('/api/testjobs/%d/' % self.testjob.id)
        self.assertEqual('myenv', data['environment'])

    def test_testjob_resubmitted_jobs(self):
        data = self.hit('/api/testjobs/%d/resubmitted_jobs/' % self.testjob5.id)
        self.assertIn(str(self.testjob5.id), data['results'][0]['parent_job'])
        self.assertEqual(self.testjob6.id, data['results'][0]['id'])

    def test_tests(self):
        data = self.hit('/api/tests/')
        self.assertEqual(list, type(data['results']))

    def test_tests_filter_by_name(self):
        data = self.hit('/api/tests/?name=test1')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(16, len(data['results']))

    def test_tests_filter_by_name_not_found(self):
        data = self.hit('/api/tests/?name=test-that-does-not-exist')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(0, len(data['results']))

    def test_tests_filter_by_metadata_name(self):
        data = self.hit('/api/tests/?metadata__name=test1')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(16, len(data['results']))

    def test_tests_filter_by_metadata_name_not_found(self):
        data = self.hit('/api/tests/?metadata__name=test-that-does-not-exist')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(0, len(data['results']))

    def test_tests_filter_by_environment(self):
        data = self.hit('/api/tests/?environment__slug=myenv')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(50, len(data['results']))

    def test_tests_filter_by_environment_not_found(self):
        data = self.hit('/api/tests/?environment__slug=mycrazyenvslug')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(0, len(data['results']))

    def test_tests_filter_by_build(self):
        data = self.hit('/api/tests/?build__version=1')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(50, len(data['results']))

    def test_tests_filter_by_build_not_found(self):
        data = self.hit('/api/tests/?build__version=this-build-should-not-exist-really')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(0, len(data['results']))

    def test_tests_with_page_size(self):
        data = self.hit('/api/tests/?limit=2')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(2, len(data['results']))

    def test_tests_minimal_fields(self):
        data = self.hit('/api/tests/?fields=name,status')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(50, len(data['results']))

        should_not_exist = {'url', 'build', 'environment', 'test_run', 'short_name', 'result', 'log', 'has_known_issues', 'suite', 'known_issues'}
        for test in data['results']:
            fields = set(test.keys())
            self.assertEqual(set(), should_not_exist & fields)
            self.assertTrue('name' in fields)
            self.assertTrue('status' in fields)
            self.assertEqual(2, len(fields))

    def test_tests_with_known_issues_fields(self):
        data = self.hit('/api/tests/?fields=known_issues')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(50, len(data['results']))

        should_not_exist = {'url', 'build', 'environment', 'test_run', 'short_name', 'result', 'log', 'has_known_issues', 'suite', 'name', 'status'}
        for test in data['results']:
            fields = set(test.keys())
            self.assertEqual(set(), should_not_exist & fields)
            self.assertTrue('known_issues' in fields)
            self.assertEqual(1, len(fields))

    def test_tests_no_status_fields(self):
        data = self.hit('/api/tests/?fields=name')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(50, len(data['results']))

        should_not_exist = {'url', 'build', 'environment', 'test_run', 'short_name', 'result', 'log', 'has_known_issues', 'suite', 'status', 'known_issues'}
        for test in data['results']:
            fields = set(test.keys())
            self.assertEqual(set(), should_not_exist & fields)
            self.assertTrue('name' in fields)
            self.assertEqual(1, len(fields))

    def test_metrics(self):
        data = self.hit('/api/metrics/')
        self.assertEqual(list, type(data['results']))

    def test_metrics_with_page_size(self):
        self.receive("2020-01-01", "myenv2", metrics={"foo": {'value': 1, 'unit': 'boxes'}, "bar/baz": {'value': 2, 'unit': None}})
        data = self.hit('/api/metrics/?limit=2')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(2, len(data['results']))

    def test_metrics_filter_by_metadata_name(self):
        data = self.hit('/api/metrics/?metadata__name=mymetric')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(1, len(data['results']))

    def test_metrics_filter_by_metadata_name_not_found(self):
        data = self.hit('/api/metrics/?metadata__name=metric-that-does-not-exist')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(0, len(data['results']))

    def test_metrics_filter_by_environment(self):
        data = self.hit('/api/metrics/?environment__slug=myenv')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(1, len(data['results']))

    def test_metrics_filter_by_environment_not_found(self):
        data = self.hit('/api/metrics/?environment__slug=mycrazyenvslug')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(0, len(data['results']))

    def test_metrics_filter_by_build(self):
        data = self.hit('/api/metrics/?build__version=1')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(1, len(data['results']))

    def test_metrics_filter_by_build_not_found(self):
        data = self.hit('/api/metrics/?build__version=this-build-should-not-exist-really')
        self.assertEqual(list, type(data['results']))
        self.assertEqual(0, len(data['results']))

    def test_testruns(self):
        data = self.hit('/api/testruns/%d/' % self.testrun.id)
        self.assertEqual(self.testrun.id, data['id'])

    def test_testruns_null_metrics_attr(self):
        data = self.hit("/api/testruns/%d/" % self.testrun4.id)
        self.assertIsNone(data["metrics"])
        self.assertIsNone(data["metrics_file"])

    def test_testruns_null_tests_attr(self):
        data = self.hit("/api/testruns/%d/" % self.testrun4.id)
        self.assertIsNone(data["tests"])
        self.assertIsNone(data["tests_file"])

    def test_testruns_not_null_metrics_attr(self):
        testrun = self.receive(
            "2020-01-01", "myenv2", metrics={"foo": {'value': 1, 'unit': 'boxes'}, "bar/baz": {'value': 2, 'unit': None}}
        )
        data = self.hit("/api/testruns/%d/" % testrun.id)
        self.assertIsNotNone(data["metrics"])
        self.assertIsNotNone(data["metrics_file"])

    def test_testruns_not_null_tests_attr(self):
        testrun = self.receive(
            "2017-01-01", "myenv2", tests={"foo": "pass", "bar": "fail"}
        )
        data = self.hit("/api/testruns/%d/" % testrun.id)
        self.assertIsNotNone(data["tests"])
        self.assertIsNotNone(data["tests_file"])

    def test_testruns_filter(self):
        data = self.hit('/api/testruns/?completed=%s&build__id=%s' % (self.testrun4.completed, self.build4.id))
        self.assertEqual(1, len(data['results']))

    def test_testruns_tests(self):
        data = self.hit('/api/testruns/%d/tests/' % self.testrun.id)
        self.assertEqual(list, type(data['results']))

    def test_testruns_metrics(self):
        data = self.hit('/api/testruns/%d/metrics/' % self.testrun.id)
        self.assertEqual(list, type(data['results']))

    def test_testruns_status(self):
        ParseTestRunData()(self.testrun)
        RecordTestRunStatus()(self.testrun)
        data = self.hit('/api/testruns/%d/status/' % self.testrun.id)
        data2 = self.hit('/api/testruns/%d/status/?suite__isnull=true' % self.testrun.id)
        self.assertEqual(3, data['count'])
        self.assertEqual(10, data['results'][0]['tests_pass'])
        self.assertEqual(8, data['results'][0]['tests_fail'])
        self.assertEqual(0, data['results'][0]['tests_xfail'])
        self.assertEqual(0, data['results'][0]['tests_skip'])
        self.assertEqual(0, data['results'][0]['metrics_summary'])
        self.assertEqual(1, data2['count'])
        self.assertEqual(None, data2['results'][0]['suite'])

    def test_testjob_definition(self):
        data = self.hit('/api/testjobs/%d/definition/' % self.testjob.id)
        self.assertEqual('foo: bar', data)

    def test_testjob_resubmit(self):
        data = self.post('/api/testjobs/%d/resubmit/' % self.testjob6.id, {})
        self.assertEqual(data.status_code, 200)
        self.assertEqual(data.json()['message'], "OK")
        user = models.User.objects.get(username='u')
        logentry_queryset = LogEntry.objects.filter(
            user_id=user.pk,
            object_id=self.testjob6.resubmitted_jobs.first().pk
        )
        self.assertEqual(
            1,
            logentry_queryset.count()
        )
        self.assertEqual(
            ADDITION,
            logentry_queryset.first().action_flag
        )

    def test_testjob_force_resubmit(self):
        data = self.post('/api/testjobs/%d/force_resubmit/' % self.testjob5.id, {})
        self.assertEqual(data.status_code, 200)
        self.assertEqual(data.json()['message'], "OK")
        user = models.User.objects.get(username='u')
        logentry_queryset = LogEntry.objects.filter(
            user_id=user.pk,
            object_id=self.testjob5.resubmitted_jobs.last().pk
        )
        self.assertEqual(
            1,
            logentry_queryset.count()
        )
        self.assertEqual(
            ADDITION,
            logentry_queryset.first().action_flag
        )

    def test_testjob_cancel(self):
        data = self.post('/api/testjobs/%d/cancel/' % self.testjob5.id, {})
        self.assertEqual(data.status_code, 200)
        self.assertEqual(data.json()['job_id'], self.testjob5.job_id)
        self.assertEqual(data.json()['status'], self.testjob5.job_status)
        user = models.User.objects.get(username='u')
        logentry_queryset = LogEntry.objects.filter(
            user_id=user.pk,
            object_id=self.testjob5.pk
        )
        self.assertEqual(
            1,
            logentry_queryset.count()
        )
        self.assertEqual(
            CHANGE,
            logentry_queryset.first().action_flag
        )

    def test_testjob_cancel_fail(self):
        data = self.post('/api/testjobs/%d/cancel/' % self.testjob2.id, {})
        self.assertEqual(data.status_code, 200)
        self.assertEqual(data.json()['job_id'], self.testjob2.job_id)
        self.assertEqual(data.json()['status'], 'Canceled')

    @patch('squad.ci.tasks.fetch.delay')
    def test_testjob_fetch(self, fetch_task):
        data = self.post('/api/testjobs/%d/fetch/' % self.testjob5.id, {})
        self.assertEqual(data.status_code, 200)
        self.assertEqual(data.json()['job_id'], self.testjob5.job_id)
        self.assertEqual(data.json()['status'], 'Queued for fetching')
        fetch_task.assert_called_with(self.testjob5.id)

    def test_testjob_backend_filter(self):
        data = self.get('/api/testjobs/?backend__implementation_type=fake')
        self.assertEqual(data.status_code, 200)
        for testjob in data.json()['results']:
            self.assertIn(f'/{self.fake_backend.id}/', testjob['backend'])

    def test_backends(self):
        data = self.hit('/api/backends/')
        self.assertEqual('foobar', data['results'][0]['name'])

    def test_backends_id_field_only(self):
        data = self.hit('/api/backends/?fields=id')
        self.assertNotIn('implementation_type', data['results'][0].keys())

    def test_backends_only_four_fields(self):
        data = self.hit('/api/backends/?fields=name,implementation_type,poll_interval,max_fetch_attempts')
        self.assertListEqual(['name', 'implementation_type', 'poll_interval', 'max_fetch_attempts'], list(data['results'][0].keys()))
        self.assertNotIn('id', data['results'][0].keys())

    def test_environments(self):
        data = self.hit('/api/environments/')
        self.assertEqual(['env-a', 'myenv'], list(sorted(set([item['slug'] for item in data['results']]))))

    def test_email_template(self):
        data = self.hit('/api/emailtemplates/')
        self.assertEqual('fooTemplate', data['results'][0]['name'])

    def test_groups(self):
        data = self.hit('/api/groups/')
        self.assertEqual('mygroup', data['results'][0]['slug'])

    def test_groups_slug_field_only(self):
        data = self.hit('/api/groups/?fields=slug')
        self.assertEqual('mygroup', data['results'][0]['slug'])
        self.assertNotIn('id', data['results'][0].keys())

    def test_patch_source(self):
        data = self.hit('/api/patchsources/')
        self.assertEqual(1, len(data['results']))

    def test_known_issues(self):
        data = self.hit('/api/knownissues/')
        self.assertEqual(2, len(data['results']))

    def test_known_issues_filter_by_environment(self):
        env_id = self.environment_a.id
        data = self.hit('/api/knownissues/?environment=%d' % env_id)
        self.assertEqual(1, len(data['results']))
        self.assertEqual('knownissue_bar', data['results'][0]['title'])

    def test_project_compare_builds_with_finished_status_and_regressions(self):
        foo_suite, _ = self.project.suites.get_or_create(slug='foo')
        foo_metadata, _ = models.SuiteMetadata.objects.get_or_create(suite=foo_suite.slug, name='dummy', kind='test')
        self.testrun4.tests.get_or_create(suite=foo_suite, metadata=foo_metadata, result=True, build=self.testrun4.build, environment=self.testrun4.environment)
        self.testrun6.tests.get_or_create(suite=foo_suite, metadata=foo_metadata, result=False, build=self.testrun6.build, environment=self.testrun6.environment)
        UpdateProjectStatus()(self.testrun4)
        UpdateProjectStatus()(self.testrun6)
        data = self.hit('/api/projects/%d/compare_builds/?baseline=%d&to_compare=%d' % (self.project.id, self.build4.id, self.build6.id))
        self.assertEqual(1, len(data['regressions']['myenv']['foo']))

    def test_project_compare_builds_by_metrics(self):
        receive = ReceiveTestRun(self.project)
        baseline = self.project.builds.create(version='baseline-metric')
        target = self.project.builds.create(version='target-metric')

        # Add regression
        self.project.thresholds.create(name='foo/regressed-metric')
        receive(baseline.version, 'myenv', metrics_file='{"foo/regressed-metric": 1}')
        receive(target.version, 'myenv', metrics_file='{"foo/regressed-metric": 2}')

        # Add improvement
        self.project.thresholds.create(name='bar/improved-metric')
        receive(baseline.version, 'myenv', metrics_file='{"bar/improved-metric": 2}')
        receive(target.version, 'myenv', metrics_file='{"bar/improved-metric": 1}')

        data = self.hit('/api/projects/%d/compare_builds/?baseline=%d&to_compare=%d&by=metrics' % (self.project.id, baseline.id, target.id))
        self.assertEqual(1, len(data['regressions']['myenv']['foo']))
        self.assertEqual(1, len(data['fixes']['myenv']['bar']))

    def test_project_compare_builds_with_non_finished_status(self):
        response = self.client.get('/api/projects/%d/compare_builds/?baseline=%d&to_compare=%d' % (self.project.id, self.build2.id, self.build3.id))
        self.assertEqual(400, response.status_code)

    def test_project_compare_builds_with_non_finished_status_force_unfinished(self):
        response = self.client.get('/api/projects/%d/compare_builds/?baseline=%d&to_compare=%d&force=1' % (self.project.id, self.build2.id, self.build3.id))
        self.assertEqual(200, response.status_code)

    def test_project_compare_builds_with_finished_status_with_verions_as_args(self):
        response = self.client.get('/api/projects/%s/compare_builds/?baseline=%s&to_compare=%s' % (self.project.id, self.build4.version, self.build6.version))
        self.assertEqual(400, response.status_code)

    def test_suites(self):
        data = self.hit('/api/suites/')
        self.assertEqual(5, data['count'])

    def test_suite_tests(self):
        foo_suite = self.project.suites.get(slug='foo')
        data = self.hit('/api/suites/%d/tests/?limit=1000' % foo_suite.id)
        self.assertEqual(54, len(data['results']))

    def test_metricthresholds_add(self):
        metric_name = 'the-threshold'
        response = self.post(
            '/api/metricthresholds/',
            {
                'project': "http://testserver/api/projects/%d/" % self.project.id,
                'name': metric_name,
            }
        )
        self.assertEqual(201, response.status_code)
        self.assertEqual(1, self.project.thresholds.filter(name=metric_name).count())
        self.hit('/api/metricthresholds/%d/' % self.project.thresholds.first().id)

    def test_metricthresholds_duplicates_all_envs(self):
        metric_name = 'duplicated-threshold-all-envs'
        response = self.post(
            '/api/metricthresholds/',
            {
                'project': "http://testserver/api/projects/%d/" % self.project.id,
                'name': metric_name,
            }
        )
        self.assertEqual(201, response.status_code)
        self.assertEqual(1, self.project.thresholds.filter(name=metric_name).count())

        # already exists project-wide
        response = self.post(
            '/api/metricthresholds/',
            {
                'project': "http://testserver/api/projects/%d/" % self.project.id,
                'name': metric_name,
                'environment': "http://testserver/api/environments/%d/" % self.environment.id
            }
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual(1, self.project.thresholds.filter(name=metric_name).count())

    def test_metricthresholds_duplicates_specific_env(self):
        metric_name = 'duplicated-threshold-specific-env'
        response = self.post(
            '/api/metricthresholds/',
            {
                'project': "http://testserver/api/projects/%d/" % self.project.id,
                'name': metric_name,
                'environment': "http://testserver/api/environments/%d/" % self.environment.id
            }
        )
        self.assertEqual(201, response.status_code)
        self.assertEqual(1, self.project.thresholds.filter(name=metric_name).count())

        # already exists an environment-specific one
        response = self.post(
            '/api/metricthresholds/',
            {
                'project': "http://testserver/api/projects/%d/" % self.project.id,
                'name': metric_name,
            }
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual(1, self.project.thresholds.filter(name=metric_name).count())
