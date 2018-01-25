from squad.core import models as core_models
from squad.core.tasks import ReceiveTestRun
from squad.ci import models
from django.test import TestCase
from django.test import Client
import json
from mock import patch

tests_file = {
    ("suite1/test%d" % i): "fail" for i in range(0, 50)
}
tests_file.update({
    ("suite2/test%d" % i): "pass" for i in range(0, 50)
})


class AllTestResultsTest(TestCase):

    def setUp(self):
        self.client = Client()
        group = core_models.Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
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

    def test_pagination(self):
        # page 1: only tests from suite1, which fail
        response = self.client.get('/mygroup/myproject/build/1/tests/?page=1')
        page1 = str(response.content)
        self.assertTrue("suite1" in page1)
        self.assertTrue("suite2" not in page1)

        # page 2: only tests from suite2, which pass
        response = self.client.get('/mygroup/myproject/build/1/tests/?page=2')
        page2 = str(response.content)
        self.assertTrue("suite1" not in page2)
        self.assertTrue("suite2" in page2)
