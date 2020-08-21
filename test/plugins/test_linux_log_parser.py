import os
from django.test import TestCase
from squad.plugins.linux_log_parser import Plugin
from squad.core.models import Group


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

    def new_testrun(self, logfile, job_id='999'):
        log = read_sample_file(logfile)
        return self.build.test_runs.create(environment=self.env, log_file=log, job_id=job_id)

    def test_detects_oops(self):
        testrun = self.new_testrun('oops.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-oops-999')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Linux version 4.4.89-01529-gb29bace', test.log)
        self.assertIn('Internal error: Oops - BUG: 0 [#1] PREEMPT SMP', test.log)
        self.assertNotIn('Kernel panic', test.log)

    def test_detects_kernel_panic(self):
        testrun = self.new_testrun('kernelpanic.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-panic-999')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Booting Linux', test.log)
        self.assertIn('Kernel panic - not syncing', test.log)
        self.assertIn('Attempted to kill init! exitcode=0x00000009', test.log)
        self.assertNotIn('Internal error: Oops', test.log)

    def test_detects_kernel_bug(self):
        testrun = self.new_testrun('oops.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-bug-999')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Booting Linux', test.log)
        self.assertIn('] BUG:', test.log)
        self.assertNotIn('Internal error: Oops', test.log)

        testrun = self.new_testrun('kernel_bug_and_invalid_opcode.log', job_id='1000')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-bug-1000')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Booting Linux', test.log)
        self.assertIn('] kernel BUG at', test.log)
        self.assertNotIn('] BUG:', test.log)
        self.assertNotIn('Internal error: Oops', test.log)

    def test_detects_kernel_invalid_opcode(self):
        testrun = self.new_testrun('kernel_bug_and_invalid_opcode.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-invalid-opcode-999')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Booting Linux', test.log)
        self.assertIn('] invalid opcode:', test.log)
        self.assertNotIn('] BUG:', test.log)
        self.assertNotIn('Internal error: Oops', test.log)

    def test_detects_multiple(self):
        testrun = self.new_testrun('multiple_issues_dmesg.log')
        self.plugin.postprocess_testrun(testrun)

        tests = testrun.tests
        test_trace = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-trace-999')
        test_panic = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-panic-999')
        test_exception = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-exception-999')
        test_warning = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-warning-999')
        test_oops = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-oops-999')
        test_fault = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-fault-999')

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
        testrun = self.new_testrun('/dev/null')
        self.plugin.postprocess_testrun(testrun)

        tests = testrun.tests
        test_trace = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-trace-999')
        test_panic = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-panic-999')
        test_exception = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-exception-999')
        test_warning = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-warning-999')
        test_oops = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-oops-999')
        test_fault = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-fault-999')

        self.assertTrue(test_trace.result)
        self.assertTrue(test_panic.result)
        self.assertTrue(test_exception.result)
        self.assertTrue(test_warning.result)
        self.assertTrue(test_oops.result)
        self.assertTrue(test_fault.result)

    def test_two_testruns_distinct_test_names(self):
        testrun1 = self.new_testrun('/dev/null', 'job1')
        testrun2 = self.new_testrun('/dev/null', 'job2')

        self.plugin.postprocess_testrun(testrun1)
        self.plugin.postprocess_testrun(testrun2)

        self.assertNotEqual(testrun1.tests.all(), testrun2.tests.all())

    def test_rcu_warning(self):
        testrun = self.new_testrun('rcu_warning.log')
        self.plugin.postprocess_testrun(testrun)

        tests = testrun.tests
        test_trace = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-trace-999')
        test_panic = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-panic-999')
        test_exception = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-exception-999')
        test_warning = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-warning-999')
        test_oops = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-oops-999')
        test_fault = tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-fault-999')

        self.assertTrue(test_trace.result)
        self.assertTrue(test_panic.result)
        self.assertTrue(test_exception.result)
        self.assertTrue(test_oops.result)
        self.assertTrue(test_fault.result)
        self.assertFalse(test_warning.result)

        self.assertIn('WARNING: suspicious RCU usage', test_warning.log)

    def test_non_string(self):
        testrun = self.build.test_runs.create(environment=self.env, job_id='1111')
        self.plugin.postprocess_testrun(testrun)

        tests = testrun.tests
        self.assertEqual(0, tests.count())

    def test_metadata_creation(self):
        testrun = self.build.test_runs.create(environment=self.env, log_file='Kernel panic - not syncing', job_id='999')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='linux-log-parser', metadata__name='check-kernel-panic-999')
        self.assertIsNotNone(test.metadata)
