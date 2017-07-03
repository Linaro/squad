from django.db import models
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string


from squad.core.models import Project, ProjectStatus, Build
from squad.core.comparison import TestComparison


class Notification(object):
    """
    Represents a notification about a project status change, that may or may
    not need to be sent.
    """

    def __init__(self, build, previous_build):
        self.build = build
        self.previous_build = previous_build

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


def send_notification(project):
    """
    E-mails a project status change notification to all subscribed email
    addresses. This should almost always be invoked in a background process.
    """
    statuses_pending_notification = ProjectStatus.objects.filter(
        build__project=project,
        notified=False,
    )
    for status in statuses_pending_notification:
        send_status_notification(status, project)


def send_status_notification(status, project=None):
    project = project or status.build.project
    previous_build = status.previous and status.previous.build or None
    notification = Notification(status.build, previous_build)

    if project.notification_strategy == Project.NOTIFY_ON_CHANGE:
        if not notification.diff or not previous_build:
            return

    __send_notification__(project, notification)
    status.notified = True
    status.save()


def notify_build(build):
    project = build.project
    previous_build = project.builds.filter(datetime__lt=build.datetime).last()
    notification = Notification(build, previous_build)
    __send_notification__(project, notification)


def __send_notification__(project, notification):
    recipients = project.subscriptions.all()
    if not recipients:
        return
    build = notification.build
    metadata = dict(sorted(build.metadata.items())) if build.metadata is not None else dict()
    summary = notification.build.test_summary
    subject_data = (
        project,
        summary.tests_total,
        summary.tests_fail,
        summary.tests_pass,
        build.version
    )
    subject = '%s: %d tests, %d failed, %d passed (build %s)' % subject_data

    context = {
        'build': build,
        'metadata': metadata,
        'previous_build': notification.previous_build,
        'regressions': notification.comparison.regressions,
        'subject': subject,
        'summary': summary,
        'notification': notification,
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
    sender = "%s <%s>" % (settings.SITE_NAME, settings.EMAIL_FROM)

    emails = [r.email for r in recipients]

    message = EmailMultiAlternatives(subject, text_message, sender, emails)
    if project.html_mail:
        message.attach_alternative(html_message, "text/html")
    message.send()
