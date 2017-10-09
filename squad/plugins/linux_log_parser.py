from collections import namedtuple
from squad.plugins import Plugin as BasePlugin


class Issue(object):
    name = None
    found = False
    done = False
    max_lines = None

    def __init__(self):
        self.__log__ = []

    @classmethod
    def find(cls, log):
        issues = [issue_type() for issue_type in cls.__subclasses__()]
        for line in log.splitlines():
            for issue in issues:
                issue.feed(line)
        return issues

    def feed(self, line):
        if self.done:
            return
        self.__feed__(line)
        if self.found:
            self.__log__.append(line)
            if self.max_lines and len(self.__log__) >= self.max_lines:
                self.done = True

    @property
    def log(self):
        return "\n".join(self.__log__)


class Oops(Issue):
    name = 'oops'
    max_lines = 50

    def __feed__(self, line):
        if "------------[ cut here ]------------" in line:
            self.found = True


class KernelPanic(Issue):
    name = 'kernel-panic'

    def __feed__(self, line):
        if 'Kernel panic - not syncing:' in line:
            self.found = True
        if '---[ end Kernel panic - not syncing' in line:
            self.done = True


class Plugin(BasePlugin):

    def postprocess_testrun(self, testrun):
        project = testrun.build.project

        suite, _ = project.suites.get_or_create(slug='linux-log-parser')
        for issue in Issue.find(testrun.log_file):
            testrun.tests.create(
                suite=suite,
                name='check-' + issue.name,
                result=(not issue.found),
                log=issue.log
            )
