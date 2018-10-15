import os
import subprocess
import shutil


from django.test import TestCase

if shutil.which('karma'):
    class TestJavascript(TestCase):
        def test_javascript(self):
            chrome_exec = shutil.which('chromium') or shutil.which('chromium-browser')
            if chrome_exec:
                os.environ["CHROME_BIN"] = chrome_exec
            else:
                self.assertTrue(False)
                print("Please install a chromium browser package in order"
                      "to run javascript unit tests.")
            self.assertEqual(
                0,
                subprocess.call(["karma", "start",
                                 "test/karma.conf.js", "--single-run"]))
else:
    print("I: skipping javascript test (karma not available)")
