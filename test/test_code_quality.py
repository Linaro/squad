import subprocess


from django.test import TestCase


class TestCodeQuality(TestCase):

    def test_flake8(self):
        subprocess.check_call(['flake8', 'squad/'])
