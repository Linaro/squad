from django.test import TestCase
from squad.core.utils import join_name, parse_name, xor, encrypt, decrypt, repeat_to_length


class TestParseName(TestCase):

    def test_simple(self):
        self.assertEqual(('foo', 'bar'), parse_name('foo/bar'))

    def test_nested(self):
        self.assertEqual(('foo/bar', 'baz'), parse_name('foo/bar/baz'))

    def test_ungrouped(self):
        self.assertEqual(('/', 'foo'), parse_name('foo'))

    def test_multiple_leading_slashes(self):
        self.assertEqual(('/', 'foo'), parse_name('//foo'))

    def test_variants_simple(self):
        self.assertEqual(('special', 'case.for[result/variants]'),
                         parse_name("special/case.for[result/variants]"))

    def test_variants_ungrouped(self):
        self.assertEqual(('/', 'case.for[result/variants]'),
                         parse_name("case.for[result/variants]"))

    def test_variants_multiple_leading_slashes(self):
        self.assertEqual(('/', 'case.for[result/variants]'),
                         parse_name("//case.for[result/variants]"))

    def test_variants_nested(self):
        self.assertEqual(('long/special', 'case.for[result/variants]'),
                         parse_name("long/special/case.for[result/variants]"))

    def test_variants_missing_opening_bracket(self):
        self.assertEqual(('long/special/case.forresult', 'variants]'),
                         parse_name("long/special/case.forresult/variants]"))


class TestJoinName(TestCase):

    def test_join_ungrouped(self):
        self.assertEqual('foo', join_name('/', 'foo'))

    def test_join_group(self):
        self.assertEqual('foo/bar', join_name('foo', 'bar'))


class TestCrypto(TestCase):

    def test_repeat_to_length(self):
        self.assertEqual('abca', repeat_to_length('abc', 4))

    def test_xor(self):
        s = 'a string'
        t = 'same len'
        ciphered = '\x12A\x1e\x11R\x05\x0b\t'
        self.assertEqual(ciphered, xor(s, t))
        self.assertEqual(s, xor(ciphered, t))

    def test_encryption(self):
        msg = 'confidential message'
        encrypted = encrypt(msg)
        decrypted = decrypt(encrypted)
        self.assertEqual(msg, decrypted)
        self.assertEqual(msg, decrypt(encrypted))
