from squad.celery import app as celery
from squad.ci.models import Backend, TestJob
from squad.ci.exceptions import SubmissionIssue
import logging


logger = logging.getLogger()


@celery.task
def poll(backend_id=None):
    if backend_id:
        backends = Backend.objects.filter(pk=backend_id)
    else:
        backends = Backend.objects.all()
    for backend in backends:
        backend.poll()


@celery.task
def fetch(job_id):
    test_job = TestJob.objects.get(pk=job_id)
    test_job.backend.fetch(test_job)


@celery.task(bind=True)
def submit(self, job_id):
    test_job = TestJob.objects.get(pk=job_id)
    try:
        test_job.backend.submit(test_job)
    except SubmissionIssue as issue:
        logger.error("submitting job %s to %s: %s" % (test_job.id, test_job.backend.name, str(issue)))
        test_job.failure = str(issue)
        test_job.save()
        if issue.retry:
            raise self.retry(exc=issue, countdown=3600)  # retry in 1 hour
