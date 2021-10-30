from django.utils import timezone
from django.test import TestCase
from dateutil.relativedelta import relativedelta

from squad.core.models import Group, ProjectStatus, MetricThreshold, SuiteMetadata
from squad.core.tasks import ReceiveTestRun, notification


def h(n):
    """
    h(n) = n hours ago
    """
    return timezone.now() - relativedelta(hours=n)


class ProjectStatusTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.project2 = self.group.projects.create(slug='myproject2')
        self.environment = self.project.environments.create(slug='theenvironment')
        self.environment_a = self.project.environments.create(slug='environment_a')
        self.suite = self.project.suites.create(slug='suite_')
        self.suite_a = self.project.suites.create(slug='suite_a')
        self.receive_testrun = ReceiveTestRun(self.project, update_project_status=False)

    def create_build(self, v, datetime=None, create_test_run=True):
        build = self.project.builds.create(version=v, datetime=datetime)
        if create_test_run:
            build.test_runs.create(environment=self.environment)
        return build

    def test_status_of_first_build(self):
        build = self.project2.builds.create(version='1122')
        status = ProjectStatus.create_or_update(build)

        self.assertEqual(build, status.build)
        self.assertIsNone(status.get_previous())

    def test_status_of_second_build(self):
        build = self.create_build('1')
        status1 = ProjectStatus.create_or_update(build)

        build2 = self.create_build('2')
        status2 = ProjectStatus.create_or_update(build2)
        self.assertEqual(status1, status2.get_previous())
        self.assertEqual(build2, status2.build)

    def test_dont_record_the_same_status_twice(self):
        build = self.create_build('1')
        status1 = ProjectStatus.create_or_update(build)
        status2 = ProjectStatus.create_or_update(build)
        self.assertEqual(status1, status2)
        self.assertEqual(1, ProjectStatus.objects.count())

    def test_wait_for_build_completion(self):
        build = self.create_build('1', datetime=h(1), create_test_run=False)
        status = ProjectStatus.create_or_update(build)
        self.assertFalse(status.finished)

    def test_first_build(self):
        build = self.create_build('1')
        status = ProjectStatus.create_or_update(build)
        self.assertEqual(build, status.build)

    def test_build_not_finished(self):
        build = self.create_build('2', datetime=h(4), create_test_run=False)
        status = ProjectStatus.create_or_update(build)
        self.assertFalse(status.finished)

    def test_force_finishing_build_on_notification_timeout_disabled(self):
        build = self.create_build('2', datetime=h(4), create_test_run=False)
        status = ProjectStatus.create_or_update(build)
        self.assertFalse(status.finished)

        build.project.force_finishing_builds_on_timeout = False
        build.project.save()

        notification.notification_timeout(status.id)
        status.refresh_from_db()
        self.assertFalse(status.finished)

    def test_force_finishing_build_on_notification_timeout_enabled(self):
        build = self.create_build('2', datetime=h(4), create_test_run=False)
        status = ProjectStatus.create_or_update(build)
        self.assertFalse(status.finished)

        build.project.force_finishing_builds_on_timeout = True
        build.project.save()

        notification.notification_timeout(status.id)
        status.refresh_from_db()
        self.assertTrue(status.finished)

    def test_test_summary(self):
        build = self.create_build('1', datetime=h(10), create_test_run=False)
        tests_json = """
            {
                "tests/foo": "pass",
                "tests/bar": "fail",
                "tests/baz": "none"
            }
        """
        self.receive_testrun(build.version, self.environment.slug, tests_file=tests_json)

        status = ProjectStatus.create_or_update(build)
        self.assertEqual(1, status.tests_pass)
        self.assertEqual(1, status.tests_fail)
        self.assertEqual(1, status.tests_skip)
        self.assertEqual(3, status.tests_total)

    def test_metrics_summary(self):
        build = self.create_build('1', datetime=h(10))
        test_run = build.test_runs.first()
        foo_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='foo', kind='metric')
        test_run.metrics.create(metadata=foo_metadata, suite=self.suite, result=2, build=test_run.build, environment=test_run.environment)
        bar_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='bar', kind='metric')
        test_run.metrics.create(metadata=bar_metadata, suite=self.suite, result=2, build=test_run.build, environment=test_run.environment)

        status = ProjectStatus.create_or_update(build)
        self.assertEqual(2.0, status.metrics_summary)

    def test_updates_data_as_new_testruns_arrive(self):
        build = self.create_build('1', datetime=h(10), create_test_run=False)

        tests_json = """
            {
                "tests/foo": "pass"
            }
        """
        self.receive_testrun(build.version, self.environment.slug, tests_file=tests_json)
        ProjectStatus.create_or_update(build)

        tests_json = """
            {
                "tests/bar": "pass",
                "tests/baz": "fail",
                "tests/qux": "none"
            }
        """
        self.receive_testrun(build.version, self.environment.slug, tests_file=tests_json)
        test_run2 = build.test_runs.create(environment=self.environment)

        metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='v1', kind='metric')
        test_run2.metrics.create(metadata=metadata, suite=self.suite, result=5.0, build=test_run2.build, environment=test_run2.environment)
        status = ProjectStatus.create_or_update(build)
        build.refresh_from_db()
        status.refresh_from_db()

        self.assertEqual(status, build.status)
        self.assertEqual(2, status.tests_pass)
        self.assertEqual(1, status.tests_fail)
        self.assertEqual(1, status.tests_skip)
        self.assertEqual(status.tests_pass, build.status.tests_pass)
        self.assertEqual(status.tests_fail, build.status.tests_fail)
        self.assertEqual(status.tests_skip, build.status.tests_skip)
        self.assertAlmostEqual(5.0, status.metrics_summary)
        self.assertEqual(status.metrics_summary, build.status.metrics_summary)

    def test_populates_last_updated(self):
        build = self.create_build('1', datetime=h(10))
        status = ProjectStatus.create_or_update(build)
        self.assertIsNotNone(status.last_updated)

    def test_updates_last_updated(self):
        build = self.create_build('1', datetime=h(10))
        test_run1 = build.test_runs.first()
        metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='foo', kind='test')
        test_run1.tests.create(build=test_run1.build, environment=test_run1.environment, metadata=metadata, suite=self.suite, result=True)
        status = ProjectStatus.create_or_update(build)
        old_date = status.last_updated

        build.test_runs.create(environment=self.environment)
        status = ProjectStatus.create_or_update(build)

        self.assertNotEqual(status.last_updated, old_date)

    def test_previous_must_be_finished(self):
        self.environment.expected_test_runs = 2
        self.environment.save()

        # finished
        build1 = self.create_build('1', datetime=h(10), create_test_run=False)
        build1.test_runs.create(environment=self.environment)
        build1.test_runs.create(environment=self.environment)
        status1 = ProjectStatus.create_or_update(build1)

        # not finished
        build2 = self.create_build('2', datetime=h(5), create_test_run=False)
        ProjectStatus.create_or_update(build2)

        # current build
        build = self.create_build('3', datetime=h(0), create_test_run=False)
        status = ProjectStatus.create_or_update(build)

        self.assertEqual(status1, status.get_previous())

    def test_previous_must_be_from_the_same_project(self):
        previous_build = self.create_build('1', datetime=h(10))
        previous = ProjectStatus.create_or_update(previous_build)

        other_project = self.group.projects.create(slug='other_project')
        other_env = other_project.environments.create(slug='other_env')
        other_build = other_project.builds.create(version='1', datetime=h(5))
        other_build.test_runs.create(environment=other_env)
        ProjectStatus.create_or_update(other_build)

        build = self.create_build('2', datetime=h(0))
        status = ProjectStatus.create_or_update(build)
        self.assertEqual(previous, status.get_previous())

    def test_zero_expected_test_runs(self):
        self.project.environments.create(slug='other_env', expected_test_runs=0)

        build = self.create_build('1')

        status = ProjectStatus.create_or_update(build)
        self.assertTrue(status.finished)

    def test_cache_test_run_counts(self):
        build = self.create_build('1', create_test_run=False)
        build.test_runs.create(environment=self.environment, completed=True)
        build.test_runs.create(environment=self.environment, completed=True)
        build.test_runs.create(environment=self.environment, completed=False)

        status = ProjectStatus.create_or_update(build)

        self.assertEqual(3, status.test_runs_total)
        self.assertEqual(2, status.test_runs_completed)
        self.assertEqual(1, status.test_runs_incomplete)

    def test_cache_test_run_counts_on_update(self):
        build = self.create_build('1', create_test_run=False)
        ProjectStatus.create_or_update(build)

        build.test_runs.create(environment=self.environment, completed=True)
        build.test_runs.create(environment=self.environment, completed=False)
        status = ProjectStatus.create_or_update(build)
        self.assertEqual(2, status.test_runs_total)
        self.assertEqual(1, status.test_runs_completed)
        self.assertEqual(1, status.test_runs_incomplete)

    def test_cache_regressions(self):
        build1 = self.create_build('1', datetime=h(10))
        build1.project.thresholds.create(name='%s/foo-metric' % self.suite.slug)
        test_run1 = build1.test_runs.first()
        foo_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='foo', kind='test')
        foo_metadata_metric, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='foo-metric', kind='metric')
        test_run1.tests.create(build=test_run1.build, environment=test_run1.environment, metadata=foo_metadata, suite=self.suite, result=True)
        test_run1.metrics.create(build=test_run1.build, environment=test_run1.environment, metadata=foo_metadata_metric, suite=self.suite, result=1)
        ProjectStatus.create_or_update(build1)

        build2 = self.create_build('2', datetime=h(9))
        test_run2 = build2.test_runs.first()
        test_run2.tests.create(build=test_run2.build, environment=test_run2.environment, metadata=foo_metadata, suite=self.suite, result=False)
        test_run2.metrics.create(build=test_run2.build, environment=test_run2.environment, metadata=foo_metadata_metric, suite=self.suite, result=2)
        status = ProjectStatus.create_or_update(build2)

        self.assertIsNotNone(status.regressions)
        self.assertIsNone(status.fixes)
        self.assertIsNotNone(status.metric_regressions)
        self.assertIsNone(status.metric_fixes)

    def test_cache_regressions_update(self):
        build1 = self.create_build('1', datetime=h(10))
        test_run1 = build1.test_runs.first()
        foo_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='foo', kind='test')
        test_run1.tests.create(build=test_run1.build, environment=test_run1.environment, metadata=foo_metadata, suite=self.suite, result=True)
        ProjectStatus.create_or_update(build1)

        build2 = self.create_build('2', datetime=h(9))
        test_run2 = build2.test_runs.first()
        test_run2.tests.create(build=test_run2.build, environment=test_run2.environment, metadata=foo_metadata, suite=self.suite, result=True)
        status1 = ProjectStatus.create_or_update(build2)

        self.assertIsNone(status1.regressions)
        self.assertIsNone(status1.fixes)

        build3 = self.create_build('3', datetime=h(8))
        test_run3 = build3.test_runs.first()
        test_run3.tests.create(build=test_run3.build, environment=test_run3.environment, metadata=foo_metadata, suite=self.suite, result=False)
        status2 = ProjectStatus.create_or_update(build3)

        self.assertIsNotNone(status2.regressions)
        self.assertIsNone(status2.fixes)

    def test_cache_fixes(self):
        build1 = self.create_build('1', datetime=h(10))
        build1.project.thresholds.create(name='%s/foo-metric' % self.suite.slug)
        test_run1 = build1.test_runs.first()
        foo_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='foo', kind='test')
        foo_metadata_metric, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='foo-metric', kind='metric')
        test_run1.tests.create(build=test_run1.build, environment=test_run1.environment, metadata=foo_metadata, suite=self.suite, result=False)
        test_run1.metrics.create(build=test_run1.build, environment=test_run1.environment, metadata=foo_metadata_metric, suite=self.suite, result=2)
        ProjectStatus.create_or_update(build1)

        build2 = self.create_build('2', datetime=h(9))
        test_run2 = build2.test_runs.first()
        test_run2.tests.create(build=test_run2.build, environment=test_run2.environment, metadata=foo_metadata, suite=self.suite, result=True)
        test_run2.metrics.create(build=test_run2.build, environment=test_run2.environment, metadata=foo_metadata_metric, suite=self.suite, result=1)
        status = ProjectStatus.create_or_update(build2)

        self.assertIsNotNone(status.fixes)
        self.assertIsNone(status.regressions)

        self.assertIsNotNone(status.metric_fixes)
        self.assertIsNone(status.metric_regressions)

    def test_cache_fixes_update(self):
        build1 = self.create_build('1', datetime=h(10))
        test_run1 = build1.test_runs.first()
        foo_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='foo', kind='test')
        test_run1.tests.create(build=test_run1.build, environment=test_run1.environment, metadata=foo_metadata, suite=self.suite, result=False)
        ProjectStatus.create_or_update(build1)

        build2 = self.create_build('2', datetime=h(9))
        test_run2 = build2.test_runs.first()
        test_run2.tests.create(build=test_run2.build, environment=test_run2.environment, metadata=foo_metadata, suite=self.suite, result=False)
        status1 = ProjectStatus.create_or_update(build2)

        self.assertIsNone(status1.fixes)
        self.assertIsNone(status1.regressions)

        build3 = self.create_build('3', datetime=h(8))
        test_run3 = build3.test_runs.first()
        test_run3.tests.create(build=test_run3.build, environment=test_run3.environment, metadata=foo_metadata, suite=self.suite, result=True)
        status2 = ProjectStatus.create_or_update(build3)

        self.assertIsNotNone(status2.fixes)
        self.assertIsNone(status2.regressions)

    def test_get_exceeded_thresholds(self):
        build = self.create_build('1')
        testrun = build.test_runs.create(environment=self.environment)
        metric1_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='metric1', kind='metric')
        metric2_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='metric2', kind='metric')
        metric3_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='metric3', kind='metric')
        testrun.metrics.create(metadata=metric1_metadata, suite=self.suite, result=3, build=testrun.build, environment=testrun.environment)
        testrun.metrics.create(metadata=metric2_metadata, suite=self.suite, result=8, build=testrun.build, environment=testrun.environment)
        testrun.metrics.create(metadata=metric3_metadata, suite=self.suite, result=5, build=testrun.build, environment=testrun.environment)

        build_a = self.create_build('2')
        testrun_a = build_a.test_runs.create(environment=self.environment_a)
        metric4_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='metric4', kind='metric')
        metric5_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='metric5', kind='metric')
        metric6_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='metric6', kind='metric')
        testrun_a.metrics.create(metadata=metric4_metadata, suite=self.suite_a, result=3, build=testrun_a.build, environment=testrun_a.environment)
        testrun_a.metrics.create(metadata=metric5_metadata, suite=self.suite_a, result=2, build=testrun_a.build, environment=testrun_a.environment)
        testrun_a.metrics.create(metadata=metric6_metadata, suite=self.suite_a, result=7, build=testrun_a.build, environment=testrun_a.environment)

        status = ProjectStatus.create_or_update(build)
        MetricThreshold.objects.create(project=self.environment.project,
                                       environment=self.environment,
                                       name='suite_/metric2', value=4,
                                       is_higher_better=False)
        thresholds = status.get_exceeded_thresholds()
        self.assertEqual(len(thresholds), 1)
        self.assertEqual(thresholds[0][1].name, 'metric2')
        self.assertEqual(thresholds[0][1].result, 8)

        status_a = ProjectStatus.create_or_update(build_a)
        MetricThreshold.objects.create(project=self.environment_a.project,
                                       environment=self.environment_a,
                                       name='suite_a/metric6', value=4,
                                       is_higher_better=True)
        thresholds = status_a.get_exceeded_thresholds()
        self.assertEqual(len(thresholds), 0)

    def test_last_build_comparison(self):
        # Test that the build that we compare against is truly the last one
        # time wise.
        build1 = self.create_build('1', datetime=h(10))
        test_run1 = build1.test_runs.first()
        foo_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='foo', kind='test')
        bar_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='bar', kind='test')
        test_run1.tests.create(build=test_run1.build, environment=test_run1.environment, metadata=foo_metadata, suite=self.suite, result=False)
        test_run1.tests.create(build=test_run1.build, environment=test_run1.environment, metadata=bar_metadata, suite=self.suite, result=False)
        ProjectStatus.create_or_update(build1)

        build2 = self.create_build('2', datetime=h(9))
        test_run2 = build2.test_runs.first()
        test_run2.tests.create(build=test_run2.build, environment=test_run2.environment, metadata=foo_metadata, suite=self.suite, result=False)
        test_run2.tests.create(build=test_run2.build, environment=test_run2.environment, metadata=bar_metadata, suite=self.suite, result=True)
        ProjectStatus.create_or_update(build2)

        build3 = self.create_build('3', datetime=h(8))
        test_run3 = build3.test_runs.first()
        test_run3.tests.create(build=test_run3.build, environment=test_run3.environment, metadata=foo_metadata, suite=self.suite, result=True)
        test_run3.tests.create(build=test_run3.build, environment=test_run3.environment, metadata=bar_metadata, suite=self.suite, result=True)
        status3 = ProjectStatus.create_or_update(build3)

        fixes3 = status3.get_fixes()
        self.assertEqual(len(fixes3['theenvironment']), 1)
        self.assertEqual(fixes3['theenvironment'][0], 'suite_/foo')

    def test_keep_baseline(self):
        # Test that baseline is kept for unfinished builds
        self.environment.expected_test_runs = 2
        self.environment.save()
        build1 = self.create_build('10', datetime=h(10))

        foo_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='foo', kind='test')
        foo2_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='foo2', kind='test')
        bar_metadata, _ = SuiteMetadata.objects.get_or_create(suite=self.suite.slug, name='bar', kind='test')

        test_run11 = build1.test_runs.first()
        test_run11.tests.create(build=test_run11.build, environment=test_run11.environment, metadata=foo_metadata, suite=self.suite, result=False)
        test_run11.tests.create(build=test_run11.build, environment=test_run11.environment, metadata=bar_metadata, suite=self.suite, result=False)
        test_run12 = build1.test_runs.create(environment=self.environment)
        test_run12.tests.create(build=test_run12.build, environment=test_run12.environment, metadata=foo2_metadata, suite=self.suite_a, result=False)
        ProjectStatus.create_or_update(build1)

        build2 = self.create_build('20', datetime=h(9))
        test_run21 = build2.test_runs.first()
        test_run21.tests.create(build=test_run21.build, environment=test_run21.environment, metadata=foo_metadata, suite=self.suite, result=False)
        test_run21.tests.create(build=test_run21.build, environment=test_run21.environment, metadata=bar_metadata, suite=self.suite, result=True)
        ProjectStatus.create_or_update(build2)

        build3 = self.create_build('30', datetime=h(8))
        test_run31 = build3.test_runs.first()
        test_run31.tests.create(build=test_run31.build, environment=test_run31.environment, metadata=foo_metadata, suite=self.suite, result=True)
        test_run31.tests.create(build=test_run31.build, environment=test_run31.environment, metadata=bar_metadata, suite=self.suite, result=True)
        ProjectStatus.create_or_update(build3)

        self.assertEqual(build2.status.baseline, build1)
        self.assertEqual(build3.status.baseline, build1)

        test_run22 = build2.test_runs.create(environment=self.environment)
        test_run22.tests.create(build=test_run22.build, environment=test_run22.environment, metadata=foo2_metadata, suite=self.suite_a, result=False)
        ProjectStatus.create_or_update(build2)

        test_run32 = build3.test_runs.create(environment=self.environment)
        test_run32.tests.create(build=test_run32.build, environment=test_run32.environment, metadata=foo2_metadata, suite=self.suite_a, result=False)
        ProjectStatus.create_or_update(build3)

        self.assertEqual(build2.status.baseline, build1)
        self.assertEqual(build3.status.baseline, build1)
