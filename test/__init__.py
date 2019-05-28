import json
import os

from unittest.runner import TextTestResult
from unittest.util import strclass

from django.test.runner import DiscoverRunner


def write_results(result, filename='tmp/tests.json'):
    data = {}
    tests = ((result.passes, 'pass'), (result.failures, 'fail'))
    for test_list, result in tests:
        for test, _ in test_list:
            name = "%s.%s" % (strclass(test.__class__), test._testMethodName)
            data[name] = result
    d = os.path.dirname(filename)
    if not os.path.exists(d):
        os.makedirs(d)
    with open(filename, 'w') as f:
        f.write(json.dumps(data, indent=4))


class TestResult(TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        super(TestResult, self).__init__(stream, descriptions, verbosity)
        self.passes = []

    def addSuccess(self, test):
        super(TestResult, self).addSuccess(test)
        self.passes.append((test, None))


class Runner(DiscoverRunner):

    def get_resultclass(self):
        return TestResult

    def suite_result(self, suite, result, **kwargs):
        write_results(result)
        return super(Runner, self).suite_result(suite, result, **kwargs)
