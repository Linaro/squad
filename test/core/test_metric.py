from django.test import TestCase
from unittest.mock import patch


from squad.core.models import Metric, Suite


class MetricTest(TestCase):

    def test_measuremens_list_none(self):
        m = Metric(measurements=None)
        self.assertEqual([], m.measurement_list)

    def test_measuremens_list_empty(self):
        m = Metric(measurements='')
        self.assertEqual([], m.measurement_list)

    def test_measuremens_list(self):
        m = Metric(measurements='1,2.5,3')
        self.assertEqual([1, 2.5, 3], m.measurement_list)

    @patch("squad.core.models.join_name", lambda x, y: 'woooops')
    def test_full_name(self):
        s = Suite()
        m = Metric(suite=s)
        self.assertEqual('woooops', m.full_name)
