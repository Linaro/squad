from squad.celery import app as celery
from squad.ci.models import Backend, TestJob
import logging


logger = logging.getLogger()


@celery.task
def poll():
    for backend in Backend.objects.all():
        backend.poll()


@celery.task
def fetch(job_id):
    test_job = TestJob.objects.get(pk=job_id)
    test_job.backend.really_fetch(test_job)


@celery.task
def submit(job_id):
    test_job = TestJob.objects.get(pk=job_id)
    test_job.backend.submit(test_job)
