import subprocess
import shutil


from unittest import TestCase

if shutil.which('flake8'):
    class TestCodeQuality(TestCase):
        def test_flake8(self):
            self.assertEqual(0, subprocess.call('flake8'))
else:
    print("I: skipping flake8 test (flake8 not available)")
