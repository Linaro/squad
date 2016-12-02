from unittest import TestCase


from squad.core.statistics import geomean


class GeomeanTest(TestCase):

    def test_basic(self):
        self.assertAlmostEqual(3.1622, geomean([1, 10]), 3)

    def test_exclude_zeroes(self):
        self.assertAlmostEqual(4, geomean([4, 0, 4]))

    def test_exclude_negative_numbers(self):
        self.assertAlmostEqual(4, geomean([4, -1, 4]))

    def test_empty_set(self):
        self.assertAlmostEqual(0, geomean([]))

    def test_set_with_only_invalid_values(self):
        self.assertAlmostEqual(0, geomean([0]))
