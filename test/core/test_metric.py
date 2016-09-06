from django.test import TestCase


from squad.core.models import Metric


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
