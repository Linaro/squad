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
        testrun = self.build.test_runs.create(environment=self.env, job_id=job_id)
        testrun.save_log_file(log)
        return testrun

    def test_detects_oops(self):
        testrun = self.new_testrun('oops.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-oops')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Linux version 4.4.89-01529-gb29bace', test.log)
        self.assertIn('Internal error: Oops - BUG: 0 [#1] PREEMPT SMP', test.log)
        self.assertNotIn('Kernel panic', test.log)

    def test_detects_kernel_panic(self):
        testrun = self.new_testrun('kernelpanic.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-panic')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Booting Linux', test.log)
        self.assertIn('Kernel panic - not syncing', test.log)
        self.assertIn('Attempted to kill init! exitcode=0x00000009', test.log)
        self.assertNotIn('Internal error: Oops', test.log)

    def test_detects_kernel_exception(self):
        testrun = self.new_testrun('kernelexceptiontrace.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-exception')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Booting Linux', test.log)
        self.assertIn('WARNING: CPU: 0 PID: 1 at kernel/smp.c:912 smp_call_function_many_cond+0x3c4/0x3c8', test.log)
        self.assertIn('5fe0: 0000000b be963e80 b6f142d9 b6f0e648 60000030 ffffffff"}', test.log)
        self.assertNotIn('Internal error: Oops', test.log)

    def test_detects_kernel_kasan(self):
        testrun = self.new_testrun('kasan.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-kasan')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Booting Linux', test.log)
        self.assertIn('==================================================================', test.log)
        self.assertIn('BUG: KASAN: slab-out-of-bounds in kmalloc_oob_right+0x190/0x3b8', test.log)
        self.assertIn('Write of size 1 at addr c6aaf473 by task kunit_try_catch/191', test.log)
        self.assertNotIn('Internal error: Oops', test.log)

    def test_detects_kernel_kfence(self):
        testrun = self.new_testrun('kfence.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-kfence')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Booting Linux', test.log)
        self.assertIn('==================================================================', test.log)
        self.assertIn('BUG: KFENCE: memory corruption in kfree+0x8c/0x174', test.log)
        self.assertIn('Corrupted memory at 0x00000000c5d55ff8 [ ! ! ! . . . . . . . . . . . . . ] (in kfence-#214):', test.log)
        self.assertNotIn('Internal error: Oops', test.log)

    def test_detects_kernel_bug(self):
        testrun = self.new_testrun('oops.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-bug')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Booting Linux', test.log)
        self.assertIn('] BUG:', test.log)
        self.assertNotIn('Internal error: Oops', test.log)

        testrun = self.new_testrun('kernel_bug_and_invalid_opcode.log', job_id='1000')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-bug')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Booting Linux', test.log)
        self.assertIn('] kernel BUG at', test.log)
        self.assertNotIn('] BUG:', test.log)
        self.assertNotIn('Internal error: Oops', test.log)

    def test_detects_kernel_invalid_opcode(self):
        testrun = self.new_testrun('kernel_bug_and_invalid_opcode.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-invalid-opcode')
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
        test_panic = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-panic')
        test_exception = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-exception')
        test_warning = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-warning')
        test_oops = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-oops')
        test_fault = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-fault')

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
        test_panic = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-panic')
        test_exception = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-exception')
        test_warning = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-warning')
        test_oops = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-oops')
        test_fault = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-fault')

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
        test_panic = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-panic')
        test_exception = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-exception')
        test_warning = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-warning')
        test_oops = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-oops')
        test_fault = tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-fault')

        self.assertTrue(test_panic.result)
        self.assertTrue(test_exception.result)
        self.assertTrue(test_oops.result)
        self.assertTrue(test_fault.result)
        self.assertFalse(test_warning.result)

        self.assertIn('WARNING: suspicious RCU usage', test_warning.log)

    def test_no_string(self):
        testrun = self.build.test_runs.create(environment=self.env, job_id='1111')
        self.plugin.postprocess_testrun(testrun)

        tests = testrun.tests.filter(result=False)
        self.assertEqual(0, tests.count())

    def test_metadata_creation(self):
        log = 'Kernel panic - not syncing'
        testrun = self.build.test_runs.create(environment=self.env, job_id='999')
        testrun.save_log_file(log)
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='log-parser-test', metadata__name='check-kernel-panic')
        self.assertIsNotNone(test.metadata)

    def test_boot_log(self):
        testrun = self.new_testrun('oops.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='log-parser-boot', metadata__name='check-kernel-oops')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Linux version 4.4.89-01529-gb29bace', test.log)
        self.assertIn('Internal error: Oops - BUG: 0 [#1] PREEMPT SMP', test.log)
        self.assertNotIn('Kernel panic', test.log)

    def test_sha_name(self):
        testrun = self.new_testrun('oops.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='log-parser-boot', metadata__name='check-kernel-oops')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Linux version 4.4.89-01529-gb29bace', test.log)
        self.assertIn('Internal error: Oops - BUG: 0 [#1] PREEMPT SMP', test.log)
        self.assertNotIn('Kernel panic', test.log)

        # Now check if a test with sha digest in the name
        test = testrun.tests.get(suite__slug='log-parser-boot', metadata__name='check-kernel-oops-a1acf2f0467782c9c2f6aeadb1d1d3cec136642b13d7231824a66ef63ee62220')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertIn('Internal error: Oops - BUG: 0 [#1] PREEMPT SMP', test.log)
        self.assertIn('Internal error: Oops - BUG: 1 [#1] PREEMPT SMP', test.log)
