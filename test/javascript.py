import os
import subprocess
import shutil


karma = os.path.join(os.path.dirname(__file__), '../node_modules/.bin/karma')


def javascript_tests():
    if not shutil.which('nodejs'):
        print("W: nodejs not available, skipping javascript tests")
        return 0
    elif os.path.exists(karma):
        chrome_exec = shutil.which('chromium') or shutil.which('chromium-browser')
        if chrome_exec:
            os.environ["CHROME_BIN"] = chrome_exec
        else:
            print("Please install a chromium browser package in order"
                  "to run javascript unit tests.")
            return 2
        return subprocess.call(
            [karma, "start", "test/karma.conf.js", "--single-run"]
        )
    else:
        print("I: skipping javascript test (karma not available)")
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(javascript_tests())
