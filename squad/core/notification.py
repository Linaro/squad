from collections import OrderedDict
from squad.mail import Message
from django.conf import settings
import django.template
import logging
import yaml
from django.template.loader import render_to_string
from re import sub


from squad.core.models import KnownIssue, NotificationDelivery, Subscription, Metric
from squad.core.comparison import TestComparison


jinja2 = django.template.engines['jinja2']
logger = logging.getLogger()


class Notification(object):
    """
    Represents a notification about a project status change, that may or may
    not need to be sent.
    """

    def __init__(self, status, previous=None):
        self.status = status
        self.build = status.build
        if previous is None:
            previous = status.get_previous()
        self.previous_build = previous and previous.build or None

    __comparison__ = None

    @property
    def comparison(self):
        if self.__comparison__ is None:
            self.__comparison__ = TestComparison(
                self.previous_build,
                self.build,
                regressions_and_fixes_only=True,
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
            return OrderedDict(sorted(self.build.metadata.items()))
        else:
            return {}

    @property
    def important_metadata(self):
        return self.build.important_metadata

    @property
    def summary(self):
        summary = self.build.test_summary
        summary.failures = self.comparison.failures
        return summary

    @property
    def recipients(self):
        emails = []
        for subscription in self.project.subscriptions.all():
            if subscription.notification_strategy == Subscription.NOTIFY_ON_CHANGE:
                if not self.previous_build or not self.diff:
                    continue
            elif subscription.notification_strategy == Subscription.NOTIFY_ON_REGRESSION:
                if not self.previous_build or \
                   len(self.comparison.regressions) == 0:
                    continue
            elif subscription.notification_strategy == Subscription.NOTIFY_ON_ERROR:
                if not self.project.project_settings:
                    logger.warn('CI_LAVA_JOB_ERROR_STATUS not set in project settings. Notification will not be sent for project %s, build %s.' % (self.project.full_name, self.build.version))
                    continue
                settings = yaml.safe_load(self.project.project_settings) or {}
                error_status = settings.get('CI_LAVA_JOB_ERROR_STATUS', None)
                if not error_status:
                    logger.warn('CI_LAVA_JOB_ERROR_STATUS not set in project settings. Notification will not be sent for project %s, build %s.' % (self.project.full_name, self.build.version))
                    continue
                if len(self.build.test_jobs.filter(job_status=error_status)) == 0:
                    continue
            email = subscription.get_email()
            if email:
                emails.append(email)
        return emails

    @property
    def known_issues(self):
        return KnownIssue.active_by_project_and_test(self.project)

    @property
    def thresholds(self):
        return self.status.get_exceeded_thresholds()

    @property
    def metrics(self):
        return Metric.objects.filter(build=self.build).all()

    @property
    def subject(self):
        return self.create_subject()

    def create_subject(self, custom_email_template=None):
        summary = self.summary
        subject_data = {
            'build': self.build.version,
            'important_metadata': self.important_metadata,
            'metadata': self.metadata,
            'project': self.project,
            'regressions': len(self.comparison.regressions),
            'tests_fail': summary.tests_fail,
            'tests_pass': summary.tests_pass,
            'tests_total': summary.tests_total,
            'tests_skip': summary.tests_skip,
        }
        if custom_email_template is None and self.project.custom_email_template is not None:
            custom_email_template = self.project.custom_email_template
        if custom_email_template and custom_email_template.subject:
            template = custom_email_template.subject
        else:
            template = '{{project}}: {{tests_total}} tests, {{tests_fail}} failed, {{tests_pass}} passed, {{tests_skip}} skipped (build {{build}})'

        return jinja2.from_string(template).render(subject_data)

    def message(self, do_html=True, custom_email_template=None):
        """
        Returns a tuple with (text_message,html_message)
        """
        context = {
            'build': self.build,
            'important_metadata': self.important_metadata,
            'metadata': self.metadata,
            'notification': self,
            'previous_build': self.previous_build,
            'regressions_grouped_by_suite': self.comparison.regressions_grouped_by_suite,
            'fixes_grouped_by_suite': self.comparison.fixes_grouped_by_suite,
            'known_issues': self.known_issues,
            'regressions': self.comparison.regressions,
            'fixes': self.comparison.fixes,
            'thresholds': self.thresholds,
            'settings': settings,
            'summary': self.summary,
            'metrics': self.metrics,
        }

        html_message = ''
        if custom_email_template:
            text_template = jinja2.from_string(custom_email_template.plain_text)
            text_message = text_template.render(context)

            if do_html:
                html_template = jinja2.from_string(custom_email_template.html)
                html_message = html_template.render(context)
        else:
            text_message = render_to_string(
                'squad/notification/diff.txt.jinja2',
                context=context,
            )
            if do_html:
                html_message = render_to_string(
                    'squad/notification/diff.html.jinja2',
                    context=context,
                )
        return (text_message, html_message)

    def send(self):
        recipients = self.recipients
        if not recipients:
            # No email is sent, but don't try to send it again
            self.mark_as_notified()
            return

        sender = "%s <%s>" % (settings.SITE_NAME, settings.EMAIL_FROM)
        subject = self.subject
        txt, html = self.message(self.project.html_mail, self.project.custom_email_template)

        if NotificationDelivery.exists(self.status, subject, txt, html):
            return

        # avoid "SMTP: 5.3.4 Message size exceeds fixed limit"
        _1MB = 1024 * 1024
        if len(txt) > _1MB or len(html) > _1MB:
            logger.error('Notification size is greater than 1MB (%i): project %s, build %s' % (len(txt), self.project.full_name, self.build.version))
            txt = 'The email got too big (> 1MB), please visit https://%s/api/builds/%i/email/?keep=7' % (settings.BASE_URL, self.build.id)
            html = '<html><body>' + txt + '</body></html>'

        message = Message(subject, txt, sender, recipients)
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

    def message(self, do_html=True, custom_email_template=None):
        txt, html = super(PreviewNotification, self).message(do_html, custom_email_template)
        txt_banner = render_to_string(
            'squad/notification/moderation.txt.jinja2',
            {
                "settings": settings,
                "status": self.status,
            }
        )
        html_banner = render_to_string(
            'squad/notification/moderation.html.jinja2',
            {
                "settings": settings,
                "status": self.status,
            }
        )
        txt = txt_banner + txt
        html = sub("<body>", "<body>\n" + html_banner, html)
        return (txt, html)


def send_status_notification(status, project=None):
    project = project or status.build.project
    send_admin_notification(status, project)

    if project.moderate_notifications and not status.approved:
        notification = PreviewNotification(status)
    else:
        notification = Notification(status)

    notification.send()


def send_admin_notification(status, project):
    build = status.build
    failed_test_jobs = build.test_jobs.filter(
        fetched=True,
        failure__isnull=False,
    )

    if not failed_test_jobs:
        return

    data = {
        'project': project,
        'build': build,
        'build_version': build.version,
        'project': project,
        'test_jobs': failed_test_jobs,
        'count': len(failed_test_jobs),
        'settings': settings,
    }
    subject = '%(build_version)s: FAILED TEST JOBS (%(count)d) -- %(project)s' % data
    sender = "%s <%s>" % (settings.SITE_NAME, settings.EMAIL_FROM)
    recipients = [r.email for r in project.admin_subscriptions.all()]
    txt = render_to_string('squad/notification/failed_test_jobs.txt.jinja2', data)

    message = Message(subject, txt, sender, recipients)
    html = ''
    if project.html_mail:
        html = render_to_string('squad/notification/failed_test_jobs.html.jinja2', data)
        message.attach_alternative(html, "text/html")

    if NotificationDelivery.exists(status, subject, txt, html):
        return

    message.send()
