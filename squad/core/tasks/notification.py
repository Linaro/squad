from squad.celery import app as celery
from squad.core.models import Project, ProjectStatus
from squad.core.notification import send_notification, send_status_notification


import logging


@celery.task
def notify_project(project_id):
    project = Project.objects.get(pk=project_id)
    send_notification(project)


@celery.task
def notify_project_status(status_id):
    status = ProjectStatus.objects.get(pk=status_id)
    send_status_notification(status)
