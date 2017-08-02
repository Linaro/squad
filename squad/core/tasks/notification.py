from django.db.models import Max
from squad.celery import app as celery
from squad.core.models import Project, ProjectStatus
from squad.core.notification import send_status_notification


import logging


@celery.task(bind=True)
def notify_project_status(self, status_id):
    try:
        status = ProjectStatus.objects.get(pk=status_id)
        send_status_notification(status)
    except ProjectStatus.DoesNotExist as not_found:
        last_id = ProjectStatus.objects.all().aggregate(Max('id'))['id__max']
        if not last_id or status_id > last_id:
            # our id is larger than the latest, the object was probably created
            # by another process but not commited to the database yet.
            raise self.retry(exc=not_found, countdown=30)  # retry in 30s
