from django.test import TestCase

from unittest.mock import patch
from squad.core.models import Test, Suite


class TestTest(TestCase):

    @patch("squad.core.models.join_name", lambda x, y: 'woooops')
    def test_full_name(self):
        s = Suite()
        t = Test(suite=s)
        self.assertEqual('woooops', t.full_name)

    def test_status_na(self):
        t = Test(result=None)
        self.assertEqual('skip/unknown', t.status)

    def test_status_pass(self):
        t = Test(result=True)
        self.assertEqual('pass', t.status)

    def test_status_fail(self):
        t = Test(result=False)
        self.assertEqual('fail', t.status)
