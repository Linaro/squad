import re
from django.test import TestCase
from django.test import Client
from django.contrib.auth.models import User


from squad.core import models
from squad.core.tasks import ReceiveTestRun
from squad.core.tasks import cleanup_build
from test.performance import count_queries


class FrontendTest(TestCase):

    def setUp(self):
        self.group = models.Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.other_project = self.group.projects.create(slug='yourproject')
        self.user = User.objects.create(username='theuser')

        self.client = Client()
        self.client.force_login(self.user)

        ReceiveTestRun(self.project)(
            version='1.0',
            environment_slug='myenv',
            log_file='log file contents ...',
            tests_file='{}',
            metrics_file='{}',
            metadata_file='{ "job_id" : "1" }',
        )
        self.test_run = models.TestRun.objects.last()
        attachment_data = "bar".encode()
        self.test_run.attachments.create(filename="foo", data=attachment_data, length=len(attachment_data))
        self.suite, _ = self.project.suites.get_or_create(slug='mysuite')
        self.test_run.tests.create(suite=self.suite, name='mytest', result=True)
        self.test = self.test_run.tests.first()

    def hit(self, url, expected_status=200):
        with count_queries('url:' + url):
            response = self.client.get(url)
        self.assertEqual(expected_status, response.status_code)
        return response

    def test_home(self):
        response = self.hit('/')
        self.assertContains(response, '<strong>mygroup</strong>', html=True, count=1)
        self.assertIsNotNone(re.search(r'2</span>\s*projects', response.content.decode()))

    def test_compare(self):
        self.hit('/_/compare/')

    def test_comparetest(self):
        self.hit('/_/comparetest/')

    def test_settings(self):
        # check if redirection to /_/settings/profile/ works
        self.hit('/_/settings/', 302)

    def test_group(self):
        self.hit('/mygroup/')

    def test_group_404(self):
        self.hit('/unexistinggroup/', 404)

    def test_project(self):
        self.hit('/mygroup/myproject/')

    def test_project_badge(self):
        self.hit('/mygroup/myproject/badge')

    def test_project_metrics(self):
        self.hit('/mygroup/myproject/metrics/')

    def test_project_test_history_404(self):
        self.hit('/mygroup/myproject/tests/foo', 404)

    def test_project_404(self):
        self.hit('/mygroup/unexistingproject/', 404)

    def test_project_no_build(self):
        self.project.builds.all().delete()
        self.hit('/mygroup/myproject/')

    def test_builds(self):
        self.hit('/mygroup/myproject/builds/')

    def test_build(self):
        self.hit('/mygroup/myproject/build/1.0/')

    def test_build_badge(self):
        self.hit('/mygroup/myproject/build/1.0/badge')

    def test_build_badge_title(self):
        self.hit('/mygroup/myproject/build/1.0/badge?title=abc')

    def test_build_badge_passrate(self):
        self.hit('/mygroup/myproject/build/1.0/badge?passrate')

    def test_build_badge_metrics(self):
        self.hit('/mygroup/myproject/build/1.0/badge?metrics')

    def test_build_badge_invalid(self):
        self.hit('/mygroup/myproject/build/1.0/badge?foo')

    def test_build_404(self):
        self.hit('/mygroup/myproject/build/999/', 404)

    def test_build_after_cleanup(self):
        self.project.data_retention_days = 180
        self.project.save()
        cleanup_build(self.project.builds.last().id)

        response = self.hit('/mygroup/myproject/build/1.0/', 404)
        self.assertIn('after 180 days', str(response.content))

    def test_build_tests_404(self):
        self.hit('/mygroup/myproject/build/999/tests/', 404)

    def test_build_testjobs_404(self):
        self.hit('/mygroup/myproject/build/999/testjobs/', 404)

    def test_build_latest_finished(self):
        self.hit('/mygroup/myproject/build/latest-finished/')

    def test_build_metadata(self):
        self.hit('/mygroup/myproject/build/1.0/metadata/')

    def test_build_latest_finished_404(self):
        self.group.projects.create(slug='otherproject')
        self.hit('/mygroup/otherproject/')
        self.hit('/mygroup/otherproject/build/latest-finished/', 404)

    def test_test_run_build_404(self):
        self.hit('/mygroup/myproject/build/2.0.missing/testrun/999/', 404)

    def test_test_run_404(self):
        self.hit('/mygroup/myproject/build/1.0/testrun/999/', 404)

    def test_attachment(self):
        data = bytes('text file', 'utf-8')
        self.test_run.attachments.create(filename='foo.txt', data=data, length=len(data))
        response = self.hit('/mygroup/myproject/build/1.0/testrun/%s/suite/%s/test/%s/attachments/foo.txt' % (self.test_run.id, self.suite.slug, self.test.name))
        self.assertEqual('text/plain', response['Content-Type'])

    def test_log(self):
        response = self.hit('/mygroup/myproject/build/1.0/testrun/%s/suite/%s/test/%s/log' % (self.test_run.id, self.suite.slug, self.test.name))
        self.assertEqual('text/plain', response['Content-Type'])

    def test_no_log(self):
        self.test_run.log_file = None
        self.test_run.save()

        response = self.client.get('/mygroup/myproject/build/1.0/testrun/%s/suite/%s/test/%s/log' % (self.test_run.id, self.suite.slug, self.test.name))
        self.assertEqual(404, response.status_code)

    def test_tests(self):
        response = self.hit('/mygroup/myproject/build/1.0/testrun/%s/suite/%s/test/%s/tests' % (self.test_run.id, self.suite.slug, self.test.name))
        self.assertEqual('application/json', response['Content-Type'])

    def test_metrics(self):
        response = self.hit('/mygroup/myproject/build/1.0/testrun/%s/suite/%s/test/%s/metrics' % (self.test_run.id, self.suite.slug, self.test.name))
        self.assertEqual('application/json', response['Content-Type'])

    def test_metadata(self):
        response = self.hit('/mygroup/myproject/build/1.0/testrun/%s/suite/%s/test/%s/metadata' % (self.test_run.id, self.suite.slug, self.test.name))
        self.assertEqual('application/json', response['Content-Type'])
