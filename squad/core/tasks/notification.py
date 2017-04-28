from squad.celery import app as celery
from squad.core.models import Project
from squad.core.notification import send_notification


import logging


@celery.task
def notify_project(project_id):
    project = Project.objects.get(pk=project_id)
    send_notification(project)


@celery.task
def notify_all_projects():
    for project in Project.objects.all():
        notify_project.delay(project.id)
