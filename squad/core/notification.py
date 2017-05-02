from django.db import models
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


from squad.core.models import ProjectStatus
from squad.core.comparison import TestComparison


class Notification(object):
    """
    Represents a notification about a project status change, that may or may
    not need to be sent.
    """

    def __init__(self, status):
        self.status = status

    @property
    def build(self):
        return self.status.build

    @property
    def previous_build(self):
        if self.status.previous:
            return self.status.previous.build

    __comparison__ = None

    @property
    def comparison(self):
        if self.__comparison__ is None:
            self.__comparison__ = TestComparison.compare_builds(
                self.previous_build,
                self.build,
            )
        return self.__comparison__

    @property
    def diff(self):
        return self.comparison.diff

    @property
    def must_be_sent(self):
        needed = self.build and self.previous_build and self.diff
        return bool(needed)


def send_notification(project):
    """
    E-mails a project status change notification to all subscribed email
    addresses. This should almost always be invoked in a background process.
    """
    project_status = ProjectStatus.create(project)
    if not project_status:
        return

    notification = Notification(project_status)
    if notification.must_be_sent:
        recipients = project.subscriptions.all()
        if not recipients:
            return
        subject = '%s: test status changed' % project
        message = render_to_string(
            'squad/notification/diff.txt',
            context={
                'notification': notification,
                'settings': settings,
            },
        )
        html_message = render_to_string(
            'squad/notification/diff.html',
            context={
                'notification': notification,
                'settings': settings,
            },
        )
        sender = "%s <%s>" % (settings.SITE_NAME, settings.EMAIL_FROM)
        for r in recipients:
            send_mail(
                subject,
                message,
                sender,
                [r.email],
                html_message=html_message,
            )
