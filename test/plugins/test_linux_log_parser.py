import os
from django.test import TestCase
from squad.plugins.linux_log_parser import Plugin
from squad.core.models import Group
from squad.ci.models import TestJob, Backend


def read_sample_file(name):
    if not name.startswith('/'):
        name = os.path.join(os.path.dirname(__file__), 'linux_log_parser', name)
    return open(name).read()


class TestLinuxLogParser(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        self.project = group.projects.create(slug='myproject', enabled_plugins_list='example')
        self.build = self.project.builds.create(version='1')
        self.env = self.project.environments.create(slug='myenv')
        self.plugin = Plugin()
        self.backend = Backend.objects.create(name='foobar')

    def new_testjob(self, logfile, name='999'):
        testjob = TestJob.objects.create(
            backend=self.backend,
            definition='',
            target=self.project,
            target_build=self.build,
            environment=self.env.slug,
            name=name
        )

        log = read_sample_file(logfile)
        testrun = self.build.test_runs.create(environment=self.env, log_file=log)
        testjob.testrun = testrun
        testjob.save()

        return testjob

    def test_detects_oops(self):
        testjob = self.new_testjob('oops.log')
        self.plugin.postprocess_testjob(testjob)

        test = testjob.testrun.tests.get(suite__slug='linux-log-parser', name='check-kernel-oops-999')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Linux version 4.4.89-01529-gb29bace', test.log)
        self.assertIn('Internal error: Oops - BUG: 0 [#1] PREEMPT SMP', test.log)
        self.assertNotIn('Kernel panic', test.log)

    def test_detects_kernel_panic(self):
        testjob = self.new_testjob('kernelpanic.log')
        self.plugin.postprocess_testjob(testjob)

        test = testjob.testrun.tests.get(suite__slug='linux-log-parser', name='check-kernel-panic-999')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Booting Linux', test.log)
        self.assertIn('Kernel panic - not syncing', test.log)
        self.assertIn('Attempted to kill init! exitcode=0x00000009', test.log)
        self.assertNotIn('Internal error: Oops', test.log)

    def test_detects_kernel_bug(self):
        testjob = self.new_testjob('oops.log')
        self.plugin.postprocess_testjob(testjob)

        test = testjob.testrun.tests.get(suite__slug='linux-log-parser', name='check-kernel-bug-999')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Booting Linux', test.log)
        self.assertIn('BUG:', test.log)
        self.assertNotIn('Internal error: Oops', test.log)

    def test_detects_multiple(self):
        testjob = self.new_testjob('multiple_issues_dmesg.log')
        self.plugin.postprocess_testjob(testjob)

        tests = testjob.testrun.tests
        test_trace = tests.get(suite__slug='linux-log-parser', name='check-kernel-trace-999')
        test_panic = tests.get(suite__slug='linux-log-parser', name='check-kernel-panic-999')
        test_exception = tests.get(suite__slug='linux-log-parser', name='check-kernel-exception-999')
        test_warning = tests.get(suite__slug='linux-log-parser', name='check-kernel-warning-999')
        test_oops = tests.get(suite__slug='linux-log-parser', name='check-kernel-oops-999')
        test_fault = tests.get(suite__slug='linux-log-parser', name='check-kernel-fault-999')

        self.assertTrue(test_trace.result)
        self.assertEqual('', test_trace.log)

        self.assertFalse(test_panic.result)
        self.assertNotIn('Boot CPU', test_panic.log)
        self.assertIn('Kernel panic - not syncing', test_panic.log)

        self.assertFalse(test_exception.result)
        self.assertNotIn('Boot CPU', test_exception.log)
        self.assertIn('------------[ cut here ]------------', test_exception.log)

        self.assertFalse(test_warning.result)
        self.assertNotIn('Boot CPU', test_warning.log)
        self.assertNotIn('Kernel panic - not syncing', test_warning.log)
        self.assertNotIn('------------[ cut here ]------------', test_warning.log)
        self.assertNotIn('Unhandled fault:', test_warning.log)
        self.assertNotIn('Oops', test_warning.log)
        self.assertIn('WARNING: CPU', test_warning.log)

        self.assertFalse(test_oops.result)
        self.assertNotIn('Boot CPU', test_oops.log)
        self.assertNotIn('Kernel panic - not syncing', test_oops.log)
        self.assertNotIn('------------[ cut here ]------------', test_oops.log)
        self.assertNotIn('WARNING: CPU', test_oops.log)
        self.assertNotIn('Unhandled fault:', test_oops.log)
        self.assertIn('Oops', test_oops.log)

        self.assertFalse(test_fault.result)
        self.assertNotIn('Boot CPU', test_fault.log)
        self.assertNotIn('Kernel panic - not syncing', test_fault.log)
        self.assertNotIn('------------[ cut here ]------------', test_fault.log)
        self.assertNotIn('WARNING: CPU', test_fault.log)
        self.assertNotIn('Oops', test_fault.log)
        self.assertIn('Unhandled fault:', test_fault.log)

    def test_pass_if_nothing_is_found(self):
        testjob = self.new_testjob('/dev/null')
        self.plugin.postprocess_testjob(testjob)

        tests = testjob.testrun.tests
        test_trace = tests.get(suite__slug='linux-log-parser', name='check-kernel-trace-999')
        test_panic = tests.get(suite__slug='linux-log-parser', name='check-kernel-panic-999')
        test_exception = tests.get(suite__slug='linux-log-parser', name='check-kernel-exception-999')
        test_warning = tests.get(suite__slug='linux-log-parser', name='check-kernel-warning-999')
        test_oops = tests.get(suite__slug='linux-log-parser', name='check-kernel-oops-999')
        test_fault = tests.get(suite__slug='linux-log-parser', name='check-kernel-fault-999')

        self.assertTrue(test_trace.result)
        self.assertTrue(test_panic.result)
        self.assertTrue(test_exception.result)
        self.assertTrue(test_warning.result)
        self.assertTrue(test_oops.result)
        self.assertTrue(test_fault.result)

    def test_two_testruns_distinct_test_names(self):
        testjob1 = self.new_testjob('/dev/null', 'job1')
        testjob2 = self.new_testjob('/dev/null', 'job2')

        self.plugin.postprocess_testjob(testjob1)
        self.plugin.postprocess_testjob(testjob2)

        self.assertNotEqual(testjob1.testrun.tests.all(), testjob2.testrun.tests.all())

    def test_rcu_warning(self):
        testjob = self.new_testjob('rcu_warning.log')
        self.plugin.postprocess_testjob(testjob)

        tests = testjob.testrun.tests
        test_trace = tests.get(suite__slug='linux-log-parser', name='check-kernel-trace-999')
        test_panic = tests.get(suite__slug='linux-log-parser', name='check-kernel-panic-999')
        test_exception = tests.get(suite__slug='linux-log-parser', name='check-kernel-exception-999')
        test_warning = tests.get(suite__slug='linux-log-parser', name='check-kernel-warning-999')
        test_oops = tests.get(suite__slug='linux-log-parser', name='check-kernel-oops-999')
        test_fault = tests.get(suite__slug='linux-log-parser', name='check-kernel-fault-999')

        self.assertTrue(test_trace.result)
        self.assertTrue(test_panic.result)
        self.assertTrue(test_exception.result)
        self.assertTrue(test_oops.result)
        self.assertTrue(test_fault.result)
        self.assertFalse(test_warning.result)

        self.assertIn('WARNING: suspicious RCU usage', test_warning.log)
