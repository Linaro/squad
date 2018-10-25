from django.test import TestCase


from squad.core import models


class TestHistoricalEmailTemplateTest(TestCase):

    def setUp(self):
        self.email_template = models.EmailTemplate()
        self.email_template.name = 'name'
        self.email_template.subject = 'subject'
        self.email_template.plain_text = 'plain text'
        self.email_template.html = 'html'
        self.email_template.save()

        self.history = models.EmailTemplate.history

    def test_history_creation(self):
        self.assertEqual(len(self.history.all()), 1)

    def test_new_version(self):
        """
        This is the main test, by default, any field that has been changed
        will trigger a new version of the object
        """

        self.email_template.name = 'other name'
        self.email_template.save()
        self.assertEqual(len(self.history.all()), 2)

        self.email_template.subject = 'other subject'
        self.email_template.save()
        self.assertEqual(len(self.history.all()), 3)

        self.email_template.plain_text = 'other plain text'
        self.email_template.save()
        self.assertEqual(len(self.history.all()), 4)

        self.email_template.html = 'other html'
        self.email_template.save()
        self.assertEqual(len(self.history.all()), 5)

        original = self.history.last().instance
        self.assertEqual(original.name, 'name')
        self.assertEqual(original.subject, 'subject')
        self.assertEqual(original.plain_text, 'plain text')
        self.assertEqual(original.html, 'html')

    def test_revert_to_previous_version(self):
        email_template_id = self.email_template.id

        self.email_template.name = 'other name'
        self.email_template.subject = 'other subject'
        self.email_template.plain_text = 'other plain text'
        self.email_template.html = 'other html'
        self.email_template.save()

        self.email_template = self.history.earliest().instance
        self.email_template.save()
        self.assertEqual(len(self.history.all()), 3)

        # Make sure to get fresh data from database
        reverted_email_template = models.EmailTemplate.objects.get(pk=email_template_id)
        self.assertEqual(reverted_email_template.name, 'name')
        self.assertEqual(reverted_email_template.subject, 'subject')
        self.assertEqual(reverted_email_template.plain_text, 'plain text')
        self.assertEqual(reverted_email_template.html, 'html')

    def test_cascading_deletion(self):
        self.email_template.delete()
        self.assertEqual(len(self.history.all()), 0)
