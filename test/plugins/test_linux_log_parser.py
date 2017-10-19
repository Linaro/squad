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

    def new_test_run(self, logfile):
        log = read_sample_file(logfile)
        return self.build.test_runs.create(environment=self.env, log_file=log)

    def test_detects_oops(self):
        testrun = self.new_test_run('oops.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='linux-log-parser', name='check-oops')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Linux version 4.4.89-01529-gb29bace', test.log)
        self.assertIn('Internal error: Oops - BUG: 0 [#1] PREEMPT SMP', test.log)
        self.assertNotIn('Kernel panic', test.log)

    def test_detects_kernel_panic(self):
        testrun = self.new_test_run('kernelpanic.log')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='linux-log-parser', name='check-kernel-panic')
        self.assertFalse(test.result)
        self.assertIsNotNone(test.log)
        self.assertNotIn('Booting Linux', test.log)
        self.assertIn('Kernel panic - not syncing', test.log)
        self.assertNotIn('Internal error: Oops', test.log)

    def test_pass_if_nothing_is_found(self):
        testrun = self.new_test_run('/dev/null')
        self.plugin.postprocess_testrun(testrun)

        test = testrun.tests.get(suite__slug='linux-log-parser', name='check-oops')
        test = testrun.tests.get(suite__slug='linux-log-parser', name='check-kernel-panic')
        self.assertTrue(test.result)
