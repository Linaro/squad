from django.core.mail import EmailMultiAlternatives


class Message(EmailMultiAlternatives):

    def __init__(self, subject, body, sender, recipients):
        super().__init__(subject, body, sender, recipients)
        self.extra_headers['Precedence'] = 'bulk'
        self.extra_headers['Auto-Submitted'] = 'auto-generated'
        self.extra_headers['X-Auto-Response-Suppress'] = 'All'
