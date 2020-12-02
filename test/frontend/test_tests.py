from squad.core import models
from squad.core.tasks import ReceiveTestRun
from django.test import TestCase
from django.test import Client
import json

tests_file = {
    ("suite1/test%d" % i): "fail" for i in range(0, 50)
}
tests_file.update({
    ("suite2/test%d" % i): "fail" for i in range(0, 50)  # xfail!
})
tests_file.update({
    ("suite3/test%d" % i): "pass" for i in range(0, 50)
})


class AllTestResultsTest(TestCase):

    def setUp(self):
        self.client = Client()
        group = models.Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
        env = project.environments.create(slug='myenv')

        for test, _ in tests_file.items():
            if test.startswith('suite2/'):
                issue = models.KnownIssue.objects.create(
                    title='foo fails',
                    test_name=test
                )
                issue.environments.add(env)

        ReceiveTestRun(project)(
            version='1',
            environment_slug='myenv',
            log_file='log file contents ...',
            tests_file=json.dumps(tests_file),
            metrics_file='{}',
            metadata_file='{ "job_id" : "1" }',
        )
        self.test_run = models.TestRun.objects.last()

    def test_basics(self):
        response = self.client.get('/mygroup/myproject/build/1/tests/')
        self.assertEqual(200, response.status_code)

    def test_pagination_page_1(self):
        # page 1: only tests from suite1 -  fail
        response = self.client.get('/mygroup/myproject/build/1/tests/?page=1')
        page1 = str(response.content)
        self.assertTrue("suite1" in page1)
        self.assertTrue("suite2" not in page1)
        self.assertTrue("suite3" not in page1)

    def test_pagination_page_2(self):
        # page 2: only tests from suite2 - xfail
        response = self.client.get('/mygroup/myproject/build/1/tests/?page=2')
        page2 = str(response.content)
        self.assertTrue("suite1" not in page2)
        self.assertTrue("suite2" in page2)
        self.assertTrue("suite3" not in page2)

    def test_pagination_page_3(self):
        # page 3: only tests from suite3 - pass
        response = self.client.get('/mygroup/myproject/build/1/tests/?page=3')
        page3 = str(response.content)
        self.assertTrue("suite1" not in page3)
        self.assertTrue("suite2" not in page3)
        self.assertTrue("suite3" in page3)

    def test_no_metadata(self):
        suite, _ = self.test_run.build.project.suites.get_or_create(slug='a-suite')
        metadata, _ = models.SuiteMetadata.objects.get_or_create(suite=suite.slug, name='no_metadata_test', kind='test')
        self.test_run.tests.create(metadata=metadata, result=False, suite=suite, build=self.test_run.build, environment=self.test_run.environment)

        response = self.client.get('/mygroup/myproject/build/1/tests/?page=2')
        self.assertEqual(200, response.status_code)

    def test_filter(self):
        response = self.client.get('/mygroup/myproject/build/1/tests/?search=test1')
        content = str(response.content)

        self.assertEqual(200, response.status_code)
        self.assertTrue('test1' in content)
        self.assertTrue('test2' not in content)


class TestRunTestsTest(TestCase):

    def setUp(self):
        self.client = Client()
        group = models.Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
        env = project.environments.create(slug='myenv')

        for test, _ in tests_file.items():
            if test.startswith('suite2/'):
                issue = models.KnownIssue.objects.create(
                    title='foo fails',
                    test_name=test
                )
                issue.environments.add(env)

        ReceiveTestRun(project)(
            version='1',
            environment_slug='myenv',
            log_file='log file contents ...',
            tests_file=json.dumps(tests_file),
            metrics_file='{}',
            metadata_file='{ "job_id" : "1" }',
        )
        self.test_run = models.TestRun.objects.last()

    def test_table_layout(self):
        response = self.client.get('/mygroup/myproject/build/1/?results_layout=table')
        self.assertEqual(200, response.status_code)

    def test_table_layout_failures_only(self):
        response = self.client.get('/mygroup/myproject/build/1/?results_layout=table&failures_only=false')
        self.assertEqual(200, response.status_code)

    def test_envbox_layout(self):
        response = self.client.get('/mygroup/myproject/build/1/?results_layout=envbox')
        self.assertEqual(200, response.status_code)

    def test_envbox_layout_failures_only(self):
        response = self.client.get('/mygroup/myproject/build/1/?results_layout=envbox&failures_only=false')
        self.assertEqual(200, response.status_code)

    def test_suitebox_layout(self):
        response = self.client.get('/mygroup/myproject/build/1/?results_layout=suitebox')
        self.assertEqual(200, response.status_code)

    def test_suitebox_layout_failures_only(self):
        response = self.client.get('/mygroup/myproject/build/1/?results_layout=suitebox&failures_only=false')
        self.assertEqual(200, response.status_code)

    def test_testrun_tests(self):
        response = self.client.get('/mygroup/myproject/build/1/testrun/%s/suite/suite1/tests/' % self.test_run.id)
        self.assertEqual(200, response.status_code)

    def test_testrun_test_details(self):
        response = self.client.get('/mygroup/myproject/build/1/testrun/%s/suite/suite1/test/test1/details/' % self.test_run.id)
        self.assertEqual(200, response.status_code)
