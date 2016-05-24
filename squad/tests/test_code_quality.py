import subprocess


from django.test import TestCase


class TestCodeQuality(TestCase):

    def test_pep8(self):
        # only ignore the long lines rule; sometimes it is very difficult to
        # keep it under 80 columns.
        subprocess.check_call(['pep8', '--ignore=E501', 'squad/'])
