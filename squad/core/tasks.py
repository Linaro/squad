from collections import defaultdict
import logging


from django.db import transaction


from squad.core.models import TestRun, Suite, Test, Metric, Status
from squad.core.data import JSONTestDataParser, JSONMetricDataParser
from squad.core.statistics import geomean


test_parser = JSONTestDataParser
metric_parser = JSONMetricDataParser
logger = logging.getLogger(__name__)


class ParseTestRunData(object):

    @staticmethod
    @transaction.atomic
    def __call__(test_run):
        if test_run.data_processed:
            return

        project = test_run.project
        for test in test_parser()(test_run.tests_file):
            suite = None
            if test['group_name']:
                suite, _ = Suite.objects.get_or_create(
                    project=project,
                    slug=test['group_name'],
                )
            Test.objects.create(
                test_run=test_run,
                suite=suite,
                name=test['test_name'],
                result=test['pass'],
            )
        for metric in metric_parser()(test_run.metrics_file):
            suite = None
            if metric['group_name']:
                suite, _ = Suite.objects.get_or_create(
                    project=project,
                    slug=metric['group_name']
                )
            Metric.objects.create(
                test_run=test_run,
                suite=suite,
                name=metric['name'],
                result=metric['result'],
                measurements=','.join([str(m) for m in metric['measurements']]),
            )

        test_run.data_processed = True
        test_run.save()


class RecordTestRunStatus(object):

    @staticmethod
    @transaction.atomic
    def __call__(testrun):
        if testrun.status_recorded:
            return

        status = defaultdict(lambda: Status(test_run=testrun))

        for test in testrun.tests.all():
            sid = test.suite_id
            if test.result:
                status[None].tests_pass = status[None].tests_pass + 1
                status[sid].tests_pass = status[sid].tests_pass + 1
            else:
                status[None].tests_fail = status[None].tests_fail + 1
                status[sid].tests_fail = status[sid].tests_fail + 1

        metrics = defaultdict(lambda: [])
        for metric in testrun.metrics.all():
            sid = metric.suite_id
            for v in metric.measurement_list:
                metrics[None].append(v)
                metrics[sid].append(v)

        for sid, values in metrics.items():
            status[sid].metrics_summary = geomean(values)
            status[sid].suite_id = sid

        for s in status.values():
            s.save()

        testrun.status_recorded = True
        testrun.save()


class ProcessTestRun(object):

    @staticmethod
    def __call__(testrun):
        ParseTestRunData()(testrun)
        RecordTestRunStatus()(testrun)


class ProcessAllTestRuns(object):

    @staticmethod
    def __call__():
        for testrun in TestRun.objects.filter(data_processed=False).all():
            logger.info("Parsing data for TestRun %d" % testrun.id)
            parser = ParseTestRunData()
            parser(testrun)
        for testrun in TestRun.objects.filter(status_recorded=False).all():
            logger.info("Recording status of TestRun %d" % testrun.id)
            recorder = RecordTestRunStatus()
            recorder(testrun)
