from django.core.exceptions import ValidationError
from django.test import TestCase


from squad.core import models


class TestEmailTemplateTest(TestCase):

    def setUp(self):
        self.email_template = models.EmailTemplate()
        self.email_template.name = 'fooTemplate'
        self.email_template.plain_text = 'text template'
        self.email_template.save()

    def test_invalid_template_syntax(self):
        emailTemplate = models.EmailTemplate.objects.get(name='fooTemplate')
        emailTemplate.subject = 'This is a {{ template'

        with self.assertRaises(ValidationError):
            emailTemplate.full_clean()

    def test_valid_template_syntax(self):
        emailTemplate = models.EmailTemplate.objects.get(name='fooTemplate')
        emailTemplate.subject = 'This is a {{ template }}'
        self.assertEqual(emailTemplate.full_clean(), None)
