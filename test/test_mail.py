from django.test import TestCase
from squad.mail import Message


class TestMessage(TestCase):

    def setUp(self):
        self.msg = Message('mail subject', 'mail body', 'sender@example.com', ['recipient@example.com'])

    def test_precedence(self):
        self.assertEqual('bulk', self.msg.extra_headers["Precedence"])

    def test_auto_submitted(self):
        self.assertEqual('auto-generated', self.msg.extra_headers['Auto-Submitted'])

    def test_x_auto_response_supress(self):
        self.assertEqual('All', self.msg.extra_headers['X-Auto-Response-Suppress'])
