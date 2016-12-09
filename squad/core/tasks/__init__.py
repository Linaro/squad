from collections import defaultdict
import json
import logging


from django.db import transaction


from squad.core.models import TestRun, Suite, Test, Metric, Status
from squad.core.data import JSONTestDataParser, JSONMetricDataParser
from squad.core.statistics import geomean
from . import exceptions


test_parser = JSONTestDataParser
metric_parser = JSONMetricDataParser
logger = logging.getLogger(__name__)


class ValidateTestRun(object):

    def __call__(self, metadata, metrics_file, tests_file):
        if metadata:
            try:
                json.loads(metadata)
            except json.decoder.JSONDecodeError as e:
                raise exceptions.InvalidMetadataJSON("metadata is not valid JSON: " + str(e))

        if metrics_file:
            try:
                json.loads(metrics_file)
            except json.decoder.JSONDecodeError as e:
                raise exceptions.InvalidMetricsDataJSON("metrics is not valid JSON: " + str(e))

        if tests_file:
            try:
                json.loads(tests_file)
            except json.decoder.JSONDecodeError as e:
                raise exceptions.InvalidTestsDataJSON("tests is not valid JSON: " + str(e))


class ReceiveTestRun(object):

    def __init__(self, project):
        self.project = project

    def __call__(self, version, environment_slug, metadata=None, metrics_file=None, tests_file=None, log_file=None):
        build, _ = self.project.builds.get_or_create(version=version)
        environment, _ = self.project.environments.get_or_create(slug=environment_slug)

        validate = ValidateTestRun()
        validate(metadata, metrics_file, tests_file)

        if metadata:
            data = json.loads(metadata)

            fields = (
                "build_url",
                "datetime",
                "job_id",
                "job_status",
                "job_url",
                "resubmit_url",
            )
            metadata_fields = {k: data[k] for k in fields if data.get(k)}
        else:
            metadata_fields = {}

        testrun = build.test_runs.create(
            environment=environment,
            tests_file=tests_file,
            metrics_file=metrics_file,
            log_file=log_file,
            **metadata_fields,
        )

        testrun.refresh_from_db()

        if not build.datetime or testrun.datetime < build.datetime:
            build.datetime = testrun.datetime
            build.save()

        processor = ProcessTestRun()
        processor(testrun)


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
