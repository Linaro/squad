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


class ValidateTestRun(object):

    def __call__(self, metadata=None, metrics_file=None, tests_file=None):
        if metadata:
            self.__validate_metadata__(metadata)

        if metrics_file:
            self.__validate_metrics(metrics_file)

        if tests_file:
            self.__validate_tests__(tests_file)

    def __validate_metadata__(self, metadata):
        try:
            metadata = json.loads(metadata)
        except json.decoder.JSONDecodeError as e:
            raise exceptions.InvalidMetadataJSON("metadata is not valid JSON: " + str(e))

        if type(metadata) != dict:
            raise exceptions.InvalidMetadata("metadata is not a object ({})")

        if "job_id" not in metadata.keys():
            raise exceptions.InvalidMetadata("job_id is mandatory in metadata")

        for key, value in metadata.items():
            if not isinstance(value, str):
                raise exceptions.InvalidMetadata("value \"%r\" is not as string" % value)

    def __validate_metrics(self, metrics_file):
        try:
            metrics = json.loads(metrics_file)
        except json.decoder.JSONDecodeError as e:
            raise exceptions.InvalidMetricsDataJSON("metrics is not valid JSON: " + str(e))

        if type(metrics) != dict:
            raise exceptions.InvalidMetricsData.type(metrics)

        for key, value in metrics.items():
            if type(value) not in [int, float, list]:
                raise exceptions.InvalidMetricsData.value(value)
            if type(value) is list:
                for item in value:
                    if type(item) not in [int, float]:
                        raise exceptions.InvalidMetricsData.value(value)

    def __validate_tests__(self, tests_file):
        try:
            tests = json.loads(tests_file)
        except json.decoder.JSONDecodeError as e:
            raise exceptions.InvalidTestsDataJSON("tests is not valid JSON: " + str(e))

        if type(tests) != dict:
            raise exceptions.InvalidTestsData.type(tests)

        for key, value in tests.items():
            if value not in ["pass", "fail"]:
                raise exceptions.InvalidTestsData.value(value)


class ReceiveTestRun(object):

    def __init__(self, project):
        self.project = project

    def __call__(self, version, environment_slug, metadata=None, metrics_file=None, tests_file=None, log_file=None, attachments={}):
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

            job_id = metadata_fields['job_id']
            if build.test_runs.filter(job_id=job_id).exists():
                raise exceptions.InvalidMetadata("There is already a test run with job_id %s" % job_id)

        else:
            metadata_fields = {}

        testrun = build.test_runs.create(
            environment=environment,
            tests_file=tests_file,
            metrics_file=metrics_file,
            log_file=log_file,
            metadata_file=metadata,
            **metadata_fields
        )

        for f, data in attachments.items():
            testrun.attachments.create(filename=f, data=data, length=len(data))

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

        for sid, s in status.items():
            s.suite_id = sid
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
            parser = ParseTestRunData()
            parser(testrun)
        for testrun in TestRun.objects.filter(status_recorded=False).all():
            recorder = RecordTestRunStatus()
            recorder(testrun)
