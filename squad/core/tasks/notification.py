from django.utils import timezone
from django.db import transaction

from squad.celery import app as celery
from squad.core.models import ProjectStatus, Build, DelayedReport
from squad.core.notification import send_status_notification

import requests


@celery.task
def maybe_notify_project_status(status_id):
    """
        This is invoked for every new TestRun a build receives.
        Notifications tasks work like the following:

        1. First notification attempt with `maybe_notify_project_status`,
           it uses the attribute `Project.wait_before_notification` which
           waits for this number of seconds AFTER `Build.datetime`. This means
           that if the build date keeps changing, notification will delay accordingly.
           NOTE: the notification will be sent only if `ProjectStatus.finished=True`,
           even after timeout expiration.

        2. Second notifcation attempt is achieved at `notification_timeout`, which
           waits for an absolute number of seconds, e.g. `Project.notification_timeout`,
           before trying to send the notification. This serves as a fallback option to
           send out notifications, even if `ProjectStatus.finished=False`.
    """

    with transaction.atomic():
        projectstatus = ProjectStatus.objects.select_for_update().get(pk=status_id)
        build = projectstatus.build
        project = build.project

        if projectstatus.notified_on_timeout is None and project.notification_timeout:
            notification_timeout.apply_async(args=[status_id], countdown=project.notification_timeout)
            projectstatus.notified_on_timeout = False
            projectstatus.save()

    if project.wait_before_notification:
        to_wait = project.wait_before_notification
        time_passed = timezone.now() - build.datetime
        if time_passed.seconds < to_wait:
            # wait time did not pass yet; try again later
            remaining_time = to_wait - time_passed.seconds + 1
            maybe_notify_project_status.apply_async(
                args=[status_id],
                countdown=remaining_time,
            )
            return

    if projectstatus.finished and not projectstatus.notified:
        # check if there are any outstanding PluginScratch objects
        if not projectstatus.build.pluginscratch_set.all():
            send_status_notification(projectstatus)

            build_id = build.id
            with transaction.atomic():
                atomic_build = Build.objects.select_for_update().get(pk=build_id)
                if atomic_build.patch_notified is False:
                    notify_patch_build_finished.delay(build_id)
                    atomic_build.patch_notified = True
                    atomic_build.save()


@celery.task
def notify_project_status(status_id):
    projectstatus = ProjectStatus.objects.get(pk=status_id)
    send_status_notification(projectstatus)


@celery.task
def notification_timeout(status_id):
    projectstatus = ProjectStatus.objects.get(pk=status_id)
    if not projectstatus.notified and not projectstatus.notified_on_timeout:
        send_status_notification(projectstatus)
        projectstatus.notified_on_timeout = True
        projectstatus.save()


@celery.task
def notify_patch_build_created(build_id):
    build = Build.objects.get(pk=build_id)
    patch_source = build.patch_source
    if patch_source:
        plugin = patch_source.get_implementation()
        plugin.notify_patch_build_created(build)


@celery.task
def notify_patch_build_finished(build_id):
    build = Build.objects.get(pk=build_id)
    patch_source = build.patch_source
    if patch_source:
        plugin = patch_source.get_implementation()
        plugin.notify_patch_build_finished(build)


@celery.task
def notify_delayed_report_callback(delayed_report_id):
    delayed_report = DelayedReport.objects.get(pk=delayed_report_id)
    if delayed_report.callback and not delayed_report.callback_notified:
        data = {'text': delayed_report.output_text, 'html': delayed_report.output_html}
        session = requests.Session()
        req = requests.Request('POST', delayed_report.callback, data=data)
        prepared_post = session.prepare_request(req)
        if delayed_report.callback_token:
            prepared_post.headers['Authorization'] = delayed_report.callback_token
            prepared_post.headers['Auth-Token'] = delayed_report.callback_token
        session.send(prepared_post)
        delayed_report.callback_notified = True
        delayed_report.save()


@celery.task
def notify_delayed_report_email(delayed_report_id):
    delayed_report = DelayedReport.objects.get(pk=delayed_report_id)
    if delayed_report.email_recipient and not delayed_report.email_recipient_notified:
        delayed_report.send()
