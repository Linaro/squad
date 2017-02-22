from django.test import TestCase

from unittest.mock import patch
from squad.core.models import Test, Suite


class TestTest(TestCase):

    @patch("squad.core.models.join_name", lambda x, y: 'woooops')
    def test_full_name(self):
        s = Suite()
        t = Test(suite=s)
        self.assertEqual('woooops', t.full_name)
