import json


from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.utils import timezone


from squad.core.models import Group, TestRun, Status, Build
from squad.core.tasks import ParseTestRunData
from squad.core.tasks import RecordTestRunStatus
from squad.core.tasks import ProcessTestRun
from squad.core.tasks import ProcessAllTestRuns
from squad.core.tasks import ReceiveTestRun


class CommonTestCase(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='mygroup')
        build = project.builds.create(version='1.0.0')
        env = project.environments.create(slug='myenv')
        self.testrun = TestRun.objects.create(
            build=build,
            environment=env,
            tests_file='{"test0": "fail", "foobar/test1": "pass"}',
            metrics_file='{"metric0": 1, "foobar/metric1": 10}',
        )


class ParseTestRunDataTest(CommonTestCase):
    def test_basics(self):
        ParseTestRunData()(self.testrun)

        self.assertEqual(2, self.testrun.tests.count())
        self.assertEqual(2, self.testrun.metrics.count())

    def test_does_not_process_twice(self):
        ParseTestRunData()(self.testrun)
        ParseTestRunData()(self.testrun)

        self.assertEqual(2, self.testrun.tests.count())
        self.assertEqual(2, self.testrun.metrics.count())


class ProcessAllTestRunsTest(CommonTestCase):

    def test_processes_all(self):
        ProcessAllTestRuns()()
        self.assertEqual(2, self.testrun.tests.count())
        self.assertEqual(3, self.testrun.status.count())


class RecordTestRunStatusTest(CommonTestCase):

    def test_basics(self):
        ParseTestRunData()(self.testrun)
        RecordTestRunStatus()(self.testrun)

        # one for each suite + general
        self.assertEqual(1, Status.objects.filter(suite=None).count())
        self.assertEqual(1, Status.objects.filter(suite__slug='/').count())
        self.assertEqual(1, Status.objects.filter(suite__slug='foobar').count())

        status = Status.objects.filter(suite=None).last()
        self.assertEqual(status.tests_pass, 1)
        self.assertEqual(status.tests_fail, 1)
        self.assertIsInstance(status.metrics_summary, float)

    def test_does_not_process_twice(self):
        ParseTestRunData()(self.testrun)
        RecordTestRunStatus()(self.testrun)
        RecordTestRunStatus()(self.testrun)
        self.assertEqual(1, Status.objects.filter(suite=None).count())


class ProcessTestRunTest(CommonTestCase):

    def test_basics(self):
        ProcessTestRun()(self.testrun)
        self.assertEqual(2, self.testrun.tests.count())
        self.assertEqual(3, self.testrun.status.count())


class ReceiveTestRunTest(TestCase):

    def test_metadata(self):
        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='mygroup')
        receive = ReceiveTestRun(project)

        today = timezone.now()

        metadata = {
            "datetime": today.isoformat(),
            "job_id": '999',
            "job_status": 'pass',
            "job_url": 'https://example.com/jobs/999',
            "resubmit_url": 'https://example.com/jobs/999',
            "build_url": 'https://example/com/builds/777',
        }

        receive('199', 'myenv', metadata=json.dumps(metadata))
        testrun = TestRun.objects.last()

        self.assertEqual(today, testrun.datetime)
        self.assertEqual(metadata['job_id'], testrun.job_id)
        self.assertEqual(metadata['job_status'], testrun.job_status)
        self.assertEqual(metadata['job_url'], testrun.job_url)
        self.assertEqual(metadata['resubmit_url'], testrun.resubmit_url)
        self.assertEqual(metadata['build_url'], testrun.build_url)

    def test_build_datetime(self):
        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='mygroup')
        receive = ReceiveTestRun(project)

        yesterday = timezone.now() - relativedelta(days=7)

        metadata = {
            "datetime": yesterday.isoformat(),
            "job_id": '999',
            "job_status": 'pass',
            "job_url": 'https://example.com/jobs/999',
            "build_url": 'https://example/com/builds/777',
        }

        receive('199', 'myenv', metadata=json.dumps(metadata))
        build = Build.objects.get(version='199')

        self.assertEqual(yesterday, build.datetime)
