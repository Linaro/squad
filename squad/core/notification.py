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


def get_notifications(status):
    __notifications__ = []
    strategy = status.build.project.notification_strategy
    if strategy == Project.NOTIFY_ALL_BUILDS:
        previous = status.previous and status.previous.build or None
        for build in status.builds:
            build_copy = Build.objects.get(pk=build.id)
            previous_copy = previous and Build.objects.get(pk=previous.id) or None
            notif = Notification(build_copy, previous_copy)
            __notifications__.append(notif)
            previous = build
    elif strategy == Project.NOTIFY_ON_CHANGE:
        if status.previous:
            notification = Notification(status.build, status.previous.build)
            if notification.diff:
                __notifications__.append(notification)
    else:
        raise RuntimeError("Invalid notification strategy: \"%s\"" % strategy)

    return __notifications__


def send_notification(project):
    """
    E-mails a project status change notification to all subscribed email
    addresses. This should almost always be invoked in a background process.
    """
    project_status = ProjectStatus.create(project)
    if not project_status:
        return

    for notification in get_notifications(project_status):
        __send_notification__(project, notification)


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
    subject = '%s: %d tests, %d failed, %d passed (build %s)' % (project, summary['total'], summary['fail'], summary['pass'], build.version)

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
    for r in recipients:
        message = EmailMultiAlternatives(subject, text_message, sender, [r.email])
        if r.html:
            message.attach_alternative(html_message, "text/html")
        message.send()
