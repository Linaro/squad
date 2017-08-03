from django.db import models
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from re import sub


from squad.core.models import Project, ProjectStatus, Build
from squad.core.comparison import TestComparison


class Notification(object):
    """
    Represents a notification about a project status change, that may or may
    not need to be sent.
    """

    def __init__(self, status):
        self.status = status
        self.build = status.build
        previous = status.get_previous()
        self.previous_build = previous and previous.build or None

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
    def project(self):
        return self.build.project

    @property
    def metadata(self):
        if self.build.metadata is not None:
            return dict(sorted(self.build.metadata.items()))
        else:
            return dict()

    @property
    def summary(self):
        return self.build.test_summary

    @property
    def recipients(self):
        return [r.email for r in self.project.subscriptions.all()]

    @property
    def subject(self):
        summary = self.summary
        subject_data = (
            self.project,
            summary.tests_total,
            summary.tests_fail,
            summary.tests_pass,
            self.build.version
        )
        return '%s: %d tests, %d failed, %d passed (build %s)' % subject_data

    @property
    def message(self):
        """
        Returns a tuple with (text_message,html_message)
        """
        context = {
            'build': self.build,
            'metadata': self.metadata,
            'previous_build': self.previous_build,
            'regressions': self.comparison.regressions,
            'summary': self.summary,
            'notification': self,
            'settings': settings,
        }

        text_message = render_to_string(
            'squad/notification/diff.txt',
            context=context,
        )
        html_message = ''
        html_message = render_to_string(
            'squad/notification/diff.html',
            context=context,
        )

        return (text_message, html_message)

    def send(self):
        recipients = self.recipients
        if not recipients:
            return

        sender = "%s <%s>" % (settings.SITE_NAME, settings.EMAIL_FROM)
        subject = self.subject
        txt, html = self.message

        message = EmailMultiAlternatives(subject, txt, sender, recipients)
        if self.project.html_mail:
            message.attach_alternative(html, "text/html")
        message.send()

        self.mark_as_notified()

    def mark_as_notified(self):
        self.status.notified = True
        self.status.save()


class PreviewNotification(Notification):

    @property
    def recipients(self):
        return [r.email for r in self.project.admin_subscriptions.all()]

    @property
    def subject(self):
        return '[PREVIEW] %s' % super(PreviewNotification, self).subject

    @property
    def message(self):
        txt, html = super(PreviewNotification, self).message
        txt_banner = render_to_string(
            'squad/notification/moderation.txt',
            {
                "settings": settings,
                "status": self.status,
            }
        )
        html_banner = render_to_string(
            'squad/notification/moderation.html',
            {
                "settings": settings,
                "status": self.status,
            }
        )
        txt = txt_banner + txt
        html = sub("<body>", "<body>\n" + html_banner, html)
        return (txt, html)

    def mark_as_notified(self):
        pass


def send_status_notification(status, project=None):
    project = project or status.build.project

    if project.moderate_notifications and not status.approved:
        notification = PreviewNotification(status)
    else:
        notification = Notification(status)

    if project.notification_strategy == Project.NOTIFY_ON_CHANGE:
        if not notification.diff or not notification.previous_build:
            return

    notification.send()
