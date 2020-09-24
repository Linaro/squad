from io import StringIO
from django.core.files import File
from unittest import TestCase

from squad.core.data import JSONMetricDataParser

TEST_DATA = """
{
    "invalid/metric1": NaN,
    "invalid/metric2": Infinity,
    "invalid/metric3": [NaN],
    "invalid/metric4": [Infinity],
    "ungrouped_int": 10,
    "ungrouped_float": 20.5,
    "ungrouped_multiple": [10,11,10,11],
    "group1/var": 50,
    "group2/var": 60
}
"""
parser = JSONMetricDataParser()


class JSONMetricDataParserTest(TestCase):

    def test_empty(self):
        self.assertEqual([], parser(File(StringIO(None))))
        self.assertEqual([], parser(File(StringIO(''))))
        self.assertEqual([], parser(File(StringIO('{}'))))

    def test_basics(self):
        data = parser(File(StringIO(TEST_DATA)))
        self.assertEqual(5, len(data))
        self.assertIsInstance(data, list)

    def test_metric_name(self):
        data = parser(File(StringIO(TEST_DATA)))
        names = [t['name'] for t in data]
        self.assertIn('ungrouped_int', names)

    def test_grouping(self):
        data = parser(File(StringIO(TEST_DATA)))
        item = [t for t in data if t['group_name'] == 'group1'][0]
        self.assertEqual(item['name'], 'var')

    def test_int(self):
        data = parser(File(StringIO(TEST_DATA)))
        item = [t for t in data if t['name'] == 'ungrouped_int'][0]
        self.assertEqual(10, item['result'])
        self.assertEqual([10], item['measurements'])

    def test_float(self):
        data = parser(File(StringIO(TEST_DATA)))
        item = [t for t in data if t['name'] == 'ungrouped_float'][0]
        self.assertEqual(20.5, item['result'])

    def test_array(self):
        data = parser(File(StringIO(TEST_DATA)))
        item = [t for t in data if t['name'] == 'ungrouped_multiple'][0]
        self.assertEqual(10.5, item['result'])
        self.assertEqual([10, 11, 10, 11], item['measurements'])

    def test_nested_group(self):
        item = parser(File(StringIO('{"foo/bar/baz": 1}')))[0]
        self.assertEqual('foo/bar', item['group_name'])
        self.assertEqual('baz', item['name'])
