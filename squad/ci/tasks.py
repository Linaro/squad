from squad.celery import app as celery
from squad.ci.models import Backend, TestJob
from squad.ci.exceptions import SubmissionIssue, FetchIssue
from celery.utils.log import get_task_logger
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string


logger = get_task_logger(__name__)


@celery.task
def poll(backend_id=None):
    if backend_id:
        backends = Backend.objects.filter(pk=backend_id)
    else:
        backends = Backend.objects.all()
    for backend in backends:
        for test_job in backend.poll():
            fetch.delay(test_job.id)


@celery.task
def fetch(job_id):
    test_job = TestJob.objects.get(pk=job_id)
    if test_job.fetch_attempts > test_job.backend.max_fetch_attempts:
        return
    logger.info("fetching %s" % test_job)
    try:
        test_job.backend.fetch(test_job)
    except FetchIssue as issue:
        logger.warn("error fetching job %s: %s" % (test_job.id, str(issue)))
        test_job.failure = str(issue)
        test_job.fetched = not issue.retry
        test_job.fetch_attempts += 1
        test_job.save()


@celery.task(bind=True)
def submit(self, job_id):
    test_job = TestJob.objects.get(pk=job_id)
    try:
        test_job.backend.submit(test_job)
        test_job.save()
    except SubmissionIssue as issue:
        logger.error("submitting job %s to %s: %s" % (test_job.id, test_job.backend.name, str(issue)))
        test_job.failure = str(issue)
        test_job.save()
        if issue.retry:
            raise self.retry(exc=issue, countdown=3600)  # retry in 1 hour


@celery.task
def send_testjob_resubmit_admin_email(job_id, resubmitted_job_id):
    test_job = TestJob.objects.get(pk=job_id)
    resubmitted_test_job = TestJob.objects.get(pk=resubmitted_job_id)
    admin_subscriptions = test_job.target.admin_subscriptions.all()
    sender = "%s <%s>" % (settings.SITE_NAME, settings.EMAIL_FROM)

    emails = [r.email for r in admin_subscriptions]
    subject = "Resubmitted: %s - TestJob %s: %s, %s, %s" % (
        test_job.target,
        test_job.job_id,
        test_job.job_status,
        test_job.environment,
        test_job.name)
    context = {
        'test_job': test_job,
        'resubmitted_job': resubmitted_test_job,
        'subject': subject,
        'settings': settings,
    }

    text_message = render_to_string(
        'squad/ci/testjob_resubmit.txt',
        context=context,
    )
    html_message = ''
    html_message = render_to_string(
        'squad/ci/testjob_resubmit.html',
        context=context,
    )

    message = EmailMultiAlternatives(subject, text_message, sender, emails)
    if test_job.target.html_mail:
        message.attach_alternative(html_message, "text/html")
    message.send()
