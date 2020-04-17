from django.core.exceptions import MultipleObjectsReturned
from django.utils import timezone
from collections import defaultdict
import json
import logging
import traceback
import uuid
import yaml


from django.db import transaction


from squad.celery import app as celery
from squad.core.models import (
    TestRun,
    Suite,
    SuiteVersion,
    SuiteMetadata,
    Test,
    Metric,
    Status,
    ProjectStatus,
    KnownIssue,
    Build,
    BuildPlaceholder,
    BuildSummary,
    Project,
    DelayedReport
)
from squad.core.data import JSONTestDataParser, JSONMetricDataParser
from squad.core.statistics import geomean
from squad.core.notification import Notification
from squad.core.plugins import apply_plugins
from squad.core.utils import join_name
from rest_framework import status
from jinja2 import TemplateSyntaxError
from . import exceptions


from .notification import maybe_notify_project_status
from .notification import notify_patch_build_created
from .notification import notify_delayed_report_callback, notify_delayed_report_email


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

        if "job_id" in metadata.keys():
            if type(metadata['job_id']) not in [int, str]:
                raise exceptions.InvalidMetadata('job_id should be an integer or a string')
            if type(metadata['job_id']) is str and '/' in metadata['job_id']:
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

    def __init__(self, project, update_project_status=True):
        self.project = project
        self.update_project_status = update_project_status

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

            job_id = metadata_fields.get('job_id')
            if job_id is None:
                metadata_fields['job_id'] = uuid.uuid4()
            elif build.test_runs.filter(job_id=job_id).exists():
                raise exceptions.DuplicatedTestJob("There is already a test run with job_id %s" % job_id)

        else:
            metadata_fields = {'job_id': uuid.uuid4()}

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

        if self.update_project_status:
            UpdateProjectStatus()(testrun)
            UpdateBuildSummary()(testrun)

        return testrun


def get_suite(test_run, suite_name):
    project = test_run.build.project
    metadata, _ = SuiteMetadata.objects.get_or_create(
        kind='suite',
        suite=suite_name,
        name='-'
    )
    suite, _ = Suite.objects.get_or_create(
        project=project,
        slug=suite_name,
        defaults={'metadata': metadata},
    )
    return suite


class ParseTestRunData(object):

    @staticmethod
    def __call__(test_run):
        if test_run.data_processed:
            return

        issues = {}
        for issue in KnownIssue.active_by_environment(test_run.environment):
            issues.setdefault(issue.test_name, [])
            issues[issue.test_name].append(issue)

        for test in test_parser()(test_run.tests_file):
            # TODO: remove check below when test_name size changes in the schema
            if len(test['test_name']) > 256:
                continue
            suite = get_suite(
                test_run,
                test['group_name']
            )
            metadata, _ = SuiteMetadata.objects.get_or_create(suite=suite.slug, name=test['test_name'], kind='test')
            full_name = join_name(suite.slug, test['test_name'])
            test_issues = issues.get(full_name, [])
            test_obj = Test.objects.create(
                test_run=test_run,
                suite=suite,
                metadata=metadata,
                name=test['test_name'],
                result=test['pass'],
                log=test['log'],
                has_known_issues=bool(test_issues),
            )
            for issue in test_issues:
                test_obj.known_issues.add(issue)

        for metric in metric_parser()(test_run.metrics_file):
            # TODO: remove check below when test_name size changes in the schema
            if len(metric['name']) > 256:
                continue
            suite = get_suite(
                test_run,
                metric['group_name']
            )
            metadata, _ = SuiteMetadata.objects.get_or_create(suite=suite.slug, name=metric['name'], kind='metric')
            Metric.objects.create(
                test_run=test_run,
                suite=suite,
                metadata=metadata,
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

    def __call_plugin__(self, plugin, testrun):
        plugin.postprocess_testrun(testrun)


@celery.task
def postprocess_test_run(test_run_id):
    testrun = None
    try:
        testrun = TestRun.objects.get(pk=test_run_id)
    except TestRun.DoesNotExist:
        # fail gracefully when test_run_id doesn't exist
        logger.error("TestRun with ID: %s not found" % test_run_id)
        return
    PostProcessTestRun()(testrun)


def get_suite_version(test_run, suite):
    if not suite:
        return None
    v = test_run.metadata.get('suite_versions', {}).get(suite.slug)
    if v:
        suite_version, _ = SuiteVersion.objects.get_or_create(suite=suite, version=v)
        return suite_version
    else:
        return None


def update_delayed_report(delayed_report, error_message, status_code, **kwargs):
    if delayed_report is None:
        try:
            delayed_report, created = DelayedReport.objects.get_or_create(**kwargs)
        except MultipleObjectsReturned:
            if "build" in kwargs.keys():
                delayed_report = kwargs["build"].delayed_reports.all()[0]   # return first available object
            else:
                delayed_report = DelayedReport.create(**kwargs)
    delayed_report.error_message = yaml.dump(error_message)
    delayed_report.status_code = status_code
    delayed_report.save()
    return delayed_report


@celery.task
def prepare_report(delayed_report_id):
    try:
        delayed_report = DelayedReport.objects.get(pk=delayed_report_id)
    except DelayedReport.DoesNotExist:
        logger.error("Cannot find report: %s" % delayed_report_id)
        return None

    build_object = delayed_report.build
    if not hasattr(build_object, "status"):
        delayed_report.status_code = status.HTTP_404_NOT_FOUND
        delayed_report.error_message = yaml.dump({"message": "Requested build status %s doesn't exist" % build_object.id})
        delayed_report.data_retention_days = 0
        delayed_report.save()
        return delayed_report

    pr_status = build_object.status
    notification = Notification(pr_status, delayed_report.baseline)
    produce_html = build_object.project.html_mail
    if delayed_report.output_format == "text/html":
        produce_html = True
    try:
        txt, html = notification.message(produce_html, delayed_report.template)
        delayed_report.output_text = txt
        delayed_report.output_html = html
        delayed_report.output_subject = notification.create_subject(delayed_report.template)
    except TemplateSyntaxError as e:
        data = {
            "lineno": e.lineno,
            "message": e.message
        }
        if delayed_report.template is not None:
            data.update({
                "txt": delayed_report.template.plain_text,
                "html": delayed_report.template.html
            })
        return update_delayed_report(delayed_report, data, status.HTTP_400_BAD_REQUEST)
    except TypeError as te:
        data = {"message": str(te)}
        if delayed_report.template is not None:
            data.update({
                "txt": delayed_report.template.plain_text,
                "html": delayed_report.template.html
            })
        return update_delayed_report(delayed_report, data, status.HTTP_400_BAD_REQUEST)

    delayed_report.status_code = status.HTTP_200_OK
    delayed_report.error_message = None
    delayed_report.save()
    if delayed_report.email_recipient:
        notify_delayed_report_email.delay(delayed_report.pk)
    if delayed_report.callback:
        notify_delayed_report_callback.delay(delayed_report.pk)
    return delayed_report


class RecordTestRunStatus(object):

    @staticmethod
    def __call__(testrun):
        if testrun.status_recorded:
            return

        status = defaultdict(lambda: Status(test_run=testrun))

        for test in testrun.tests.all():
            sid = test.suite_id
            if test.result is True:
                status[None].tests_pass += 1
                status[sid].tests_pass += 1
            elif test.result is False:
                if test.known_issues.exists():
                    status[None].tests_xfail += 1
                    status[sid].tests_xfail += 1
                else:
                    status[None].tests_fail += 1
                    status[sid].tests_fail += 1
            else:
                status[None].tests_skip += 1
                status[sid].tests_skip += 1

        metrics = defaultdict(lambda: [])
        for metric in testrun.metrics.all():
            sid = metric.suite_id
            for v in metric.measurement_list:
                metrics[None].append(v)
                metrics[sid].append(v)

        # One Status has many test suites and each of one of them
        # has their own summary (i.e. geomean).
        # The status having no test suite (suite=None) represent
        # the TestRun's summary
        if len(metrics[None]):
            status[None].has_metrics = True
        for sid, values in metrics.items():
            status[sid].metrics_summary = geomean(values)
            status[sid].has_metrics = True

        for sid, s in status.items():
            s.suite_id = sid
            s.suite_version = get_suite_version(testrun, s.suite)
            s.save()

        testrun.status_recorded = True
        testrun.save()


class UpdateProjectStatus(object):

    @staticmethod
    def __call__(testrun):
        projectstatus = ProjectStatus.create_or_update(testrun.build)
        maybe_notify_project_status.delay(projectstatus.id)


class UpdateBuildSummary(object):

    @staticmethod
    def __call__(testrun):
        BuildSummary.create_or_update(testrun.build, testrun.environment)


class ProcessTestRun(object):

    @staticmethod
    def __call__(testrun):
        with transaction.atomic():
            ParseTestRunData()(testrun)
            PostProcessTestRun()(testrun)
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


class CreateBuild(object):

    def __init__(self, project):
        self.project = project

    def __call__(self, version, patch_source=None, patch_id=None, patch_baseline=None):
        defaults = {
            'patch_source': patch_source,
            'patch_id': patch_id,
            'patch_baseline': patch_baseline,
        }
        build, _ = self.project.builds.get_or_create(
            version=version,
            defaults=defaults,
        )
        if build.patch_source and build.patch_id:
            notify_patch_build_created.delay(build.id)
        return build


@celery.task
def cleanup_old_builds():
    for project in Project.objects.filter(data_retention_days__gt=0):
        start = timezone.now() - timezone.timedelta(project.data_retention_days)
        builds = project.builds.filter(
            created_at__lt=start
        ).exclude(
            keep_data=True
        ).values('id')
        for entry in builds:
            cleanup_build.delay(entry['id'])


@celery.task
def remove_delayed_reports():
    now = timezone.now()
    for report in DelayedReport.objects.all():
        if now - report.created_at > timezone.timedelta(report.data_retention_days):
            report.delete()


@celery.task
@transaction.atomic
def cleanup_build(build_id):
    build = Build.objects.get(pk=build_id)
    BuildPlaceholder.objects.create(project=build.project, version=build.version)
    build.delete()
