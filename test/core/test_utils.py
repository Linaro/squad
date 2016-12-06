from django.test import TestCase
from squad.core.utils import join_name, parse_name


class TestParseName(TestCase):

    def test_simple(self):
        self.assertEqual(('foo', 'bar'), parse_name('foo/bar'))

    def test_nested(self):
        self.assertEqual(('foo/bar', 'baz'), parse_name('foo/bar/baz'))

    def test_ungrouped(self):
        self.assertEqual(('/', 'foo'), parse_name('foo'))

    def test_multiple_leading_slashes(self):
        self.assertEqual(('/', 'foo'), parse_name('//foo'))


class TestJoinName(TestCase):

    def test_join_ungrouped(self):
        self.assertEqual('foo', join_name('/', 'foo'))

    def test_join_group(self):
        self.assertEqual('foo/bar', join_name('foo', 'bar'))
