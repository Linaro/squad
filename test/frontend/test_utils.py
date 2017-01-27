from django.test import TestCase

from squad.frontend.utils import file_type


class FileTypeTest(TestCase):

    def test_text(self):
        self.assertEqual('text', file_type('foo.txt'))

    def test_code(self):
        self.assertEqual('code', file_type('foo.py'))
        self.assertEqual('code', file_type('foo.sh'))

    def test_image(self):
        self.assertEqual('image', file_type('foo.png'))
        self.assertEqual('image', file_type('foo.jpg'))
