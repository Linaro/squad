from collections import defaultdict
import json
import logging
import traceback
import uuid


from django.db import transaction


from squad.core.models import TestRun, Suite, Test, Metric, Status, ProjectStatus
from squad.core.data import JSONTestDataParser, JSONMetricDataParser
from squad.core.statistics import geomean
from squad.plugins import apply_plugins
from . import exceptions


from .notification import notify_project_status, maybe_notify_project_status


test_parser = JSONTestDataParser
metric_parser = JSONMetricDataParser


logger = logging.getLogger()


class ValidateTestRun(object):

    def __call__(self, metadata_file=None, metrics_file=None, tests_file=None):
        if metadata_file:
            self.__validate_metadata__(metadata_file)

        if metrics_file:
            self.__validate_metrics(metrics_file)

        if tests_file:
            self.__validate_tests__(tests_file)

    def __validate_metadata__(self, metadata_json):
        try:
            metadata = json.loads(metadata_json)
        except json.decoder.JSONDecodeError as e:
            raise exceptions.InvalidMetadataJSON("metadata is not valid JSON: " + str(e) + "\n" + metadata_json)

        if type(metadata) != dict:
            raise exceptions.InvalidMetadata("metadata is not a object ({})")

        if "job_id" not in metadata.keys():
            raise exceptions.InvalidMetadata("job_id is mandatory in metadata")
        elif '/' in metadata['job_id']:
                raise exceptions.InvalidMetadata('job_id cannot contain the "/" character')

    def __validate_metrics(self, metrics_file):
        try:
            metrics = json.loads(metrics_file)
        except json.decoder.JSONDecodeError as e:
            raise exceptions.InvalidMetricsDataJSON("metrics is not valid JSON: " + str(e) + "\n" + metrics_file)

        if type(metrics) != dict:
            raise exceptions.InvalidMetricsData.type(metrics)

        for key, value in metrics.items():
            if type(value) is str:
                try:
                    value = float(value)
                except ValueError:
                    raise exceptions.InvalidMetricsData.value(value)
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
            raise exceptions.InvalidTestsDataJSON("tests is not valid JSON: " + str(e) + "\n" + tests_file)

        if type(tests) != dict:
            raise exceptions.InvalidTestsData.type(tests)


class ReceiveTestRun(object):

    def __init__(self, project):
        self.project = project

    SPECIAL_METADATA_FIELDS = (
        "build_url",
        "datetime",
        "job_id",
        "job_status",
        "job_url",
        "resubmit_url",
    )

    def __call__(self, version, environment_slug, metadata_file=None, metrics_file=None, tests_file=None, log_file=None, attachments={}, completed=True):
        build, _ = self.project.builds.get_or_create(version=version)
        environment, _ = self.project.environments.get_or_create(slug=environment_slug)

        validate = ValidateTestRun()
        validate(metadata_file, metrics_file, tests_file)

        if metadata_file:
            data = json.loads(metadata_file)

            fields = self.SPECIAL_METADATA_FIELDS
            metadata_fields = {k: data[k] for k in fields if data.get(k)}

            job_id = metadata_fields['job_id']
            if build.test_runs.filter(job_id=job_id).exists():
                raise exceptions.InvalidMetadata("There is already a test run with job_id %s" % job_id)

        else:
            metadata_fields = {}

        if 'job_id' not in metadata_fields:
            metadata_fields['job_id'] = uuid.uuid4()

        if log_file:
            log_file = log_file.replace("\x00", "")

        testrun = build.test_runs.create(
            environment=environment,
            tests_file=tests_file,
            metrics_file=metrics_file,
            log_file=log_file,
            metadata_file=metadata_file,
            completed=completed,
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
        return testrun


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


class PostProcessTestRun(object):

    def __call__(self, testrun):
        project = testrun.build.project
        for plugin in apply_plugins(project.enabled_plugins):
            try:
                self.__call_plugin__(plugin, testrun)
            except Exception as e:
                logger.error("Plugin postprocessing error: " + str(e) + "\n" + traceback.format_exc())

    @transaction.atomic
    def __call_plugin__(self, plugin, testrun):
        plugin.postprocess_testrun(testrun)


class RecordTestRunStatus(object):

    @staticmethod
    @transaction.atomic
    def __call__(testrun):
        if testrun.status_recorded:
            return

        status = defaultdict(lambda: Status(test_run=testrun))

        for test in testrun.tests.all():
            sid = test.suite_id
            if test.result is True:
                status[None].tests_pass = status[None].tests_pass + 1
                status[sid].tests_pass = status[sid].tests_pass + 1
            elif test.result is False:
                status[None].tests_fail = status[None].tests_fail + 1
                status[sid].tests_fail = status[sid].tests_fail + 1
            else:
                status[None].tests_skip = status[None].tests_skip + 1
                status[sid].tests_skip = status[sid].tests_skip + 1

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


class UpdateProjectStatus(object):

    @staticmethod
    def __call__(testrun):
        projectstatus = ProjectStatus.create_or_update(testrun.build)
        try:
            maybe_notify_project_status.delay(projectstatus.id)
        except OSError as e:
            # can't request background task for some reason; log the error
            # and continue.
            #
            # This will happen as "OSError: [Errno 111] Connection refused"
            # in development environments without a running AMQP server,
            # but also on production setups that are not running the
            # background job processes because they don't need email
            # notifications or CI integration
            logger.error("Cannot schedule notification: " + str(e) + "\n" + traceback.format_exc())


class ProcessTestRun(object):

    @staticmethod
    def __call__(testrun):
        ParseTestRunData()(testrun)
        PostProcessTestRun()(testrun)
        RecordTestRunStatus()(testrun)
        UpdateProjectStatus()(testrun)


class ProcessAllTestRuns(object):

    @staticmethod
    def __call__():
        for testrun in TestRun.objects.filter(data_processed=False).all():
            parser = ParseTestRunData()
            parser(testrun)
        for testrun in TestRun.objects.filter(status_recorded=False).all():
            recorder = RecordTestRunStatus()
            recorder(testrun)
