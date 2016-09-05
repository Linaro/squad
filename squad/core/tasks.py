import logging


from django.db import transaction


from squad.core.models import TestRun, Suite, Test, Metric
from squad.core.data import JSONTestDataParser, JSONMetricDataParser


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


class ParseAllTestRuns(object):

    @staticmethod
    def __call__():
        for testrun in TestRun.objects.filter(data_processed=False).all():
            logger.info("Parsing data for TestRun %d" % testrun.id)
            parser = ParseTestRunData()
            parser(testrun)
