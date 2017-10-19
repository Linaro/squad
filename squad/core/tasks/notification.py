from django.db.models import Max
from squad.celery import app as celery
from squad.core.models import Project, ProjectStatus
from squad.core.notification import send_status_notification


import logging


@celery.task
def notify_project_status(status_id):
    projectstatus = ProjectStatus.objects.get(pk=status_id)
    send_status_notification(projectstatus)
