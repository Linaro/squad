from django.test import TestCase
from fnmatch import fnmatch
import re
import shutil
import subprocess


ALLOWED_MODULE_DEPENDENCIES = (
    ('squad', 'squad.celery'),
    ('squad.api', 'squad.api'),
    ('squad.api', 'squad.ci'),
    ('squad.api', 'squad.core'),
    ('squad.api', 'squad.http'),
    ('squad.ci', 'squad.ci'),
    ('squad.ci', 'squad.core'),
    ('squad.core', 'squad.core'),
    ('squad.core.admin', 'squad.plugins'),
    ('squad.core.tasks', 'squad.plugins'),
    ('squad.frontend', 'squad.core'),
    ('squad.frontend', 'squad.frontend'),
    ('squad.frontend', 'squad.http'),
    ('squad.frontend', 'squad.ci'),
    ('squad.http', 'squad.core'),
    ('squad.run', 'squad.manage'),
    ('squad.run', 'squad.version'),
    ('squad.plugins.*', 'squad.plugins'),
    ('squad.settings', 'squad.core'),
)


def filename2modulename(f):
    dotted = re.sub('/', '.', f)
    return re.sub('.py$', '', dotted)


def match_module(contained, container):
    return fnmatch(contained, container) or contained.startswith(container + '.')


def check_dependency(file1, file2):
    if not file2:
        return True, None

    m1 = filename2modulename(file1)
    m2 = filename2modulename(file2)
    for src, dest in ALLOWED_MODULE_DEPENDENCIES:
        if match_module(m1, src) and match_module(m2, dest):
            return True, None
    msg = "Dependency violates architecture: %s → %s (%s)" % (m1, m2, file1)
    return False, msg


if shutil.which('sfood'):
    class ArchitectureConformanceTest(TestCase):
        def test_architecture(self):
            data = subprocess.check_output(
                ['sfood', '--internal-only', 'squad'],
                stderr=subprocess.DEVNULL,
            )
            for line in data.splitlines():
                (path1, file1), (path2, file2) = eval(line)
                res, msg = check_dependency(file1, file2)
                self.assertTrue(res, msg)
else:
    print("I: skipping architecture conformance tests (snakefood not available)")

if __name__ == '__main__':
    print("digraph squad {")
    for src, dest in ALLOWED_MODULE_DEPENDENCIES:
        if src != dest:
            print('"%s" -> "%s";' % (src, dest))
    print("}")
