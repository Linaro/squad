from unittest import TestCase

from squad.core.data import JSONMetricDataParser

TEST_DATA = """
{
"invalid/metric1": {"value": NaN, "unit": ""},
"invalid/metric2": {"value": Infinity, "unit": ""},
"invalid/metric3": {"value": [NaN], "unit": ""},
"invalid/metric4": {"value": [Infinity], "unit": ""},
"ungrouped_int": {"value": 10, "unit": "seconds"},
"ungrouped_float": {"value": 20.5, "unit": "kb"},
"ungrouped_multiple": {"value": [10,11,10,11], "unit": "clicks"},
"group1/var": {"value": 50, "unit": "hours"},
"group2/var": {"value": 60, "unit": "miles"}
}
"""
parser = JSONMetricDataParser()


class JSONMetricDataParserTest(TestCase):

    def test_empty(self):
        self.assertEqual([], parser(None))
        self.assertEqual([], parser(''))
        self.assertEqual([], parser('{}'))

    def test_basics(self):
        data = parser(TEST_DATA)
        self.assertEqual(5, len(data))
        self.assertIsInstance(data, list)

    def test_metric_name(self):
        data = parser(TEST_DATA)
        names = [t['name'] for t in data]
        self.assertIn('ungrouped_int', names)

    def test_grouping(self):
        data = parser(TEST_DATA)
        item = [t for t in data if t['group_name'] == 'group1'][0]
        self.assertEqual(item['name'], 'var')

    def test_int(self):
        data = parser(TEST_DATA)
        item = [t for t in data if t['name'] == 'ungrouped_int'][0]
        self.assertEqual(10, item['result'])
        self.assertEqual([10], item['measurements'])

    def test_float(self):
        data = parser(TEST_DATA)
        item = [t for t in data if t['name'] == 'ungrouped_float'][0]
        self.assertEqual(20.5, item['result'])

    def test_array(self):
        data = parser(TEST_DATA)
        item = [t for t in data if t['name'] == 'ungrouped_multiple'][0]
        self.assertEqual(10.5, item['result'])
        self.assertEqual([10, 11, 10, 11], item['measurements'])

    def test_nested_group(self):
        item = parser('{"foo/bar/baz": {"value": 1, "unit": ""}}')[0]
        self.assertEqual('foo/bar', item['group_name'])
        self.assertEqual('baz', item['name'])
