import traceback
from squad.celery import app as celery
from squad.core.plugins import get_plugin_instance
from squad.ci.models import Backend, TestJob
from squad.ci.exceptions import SubmissionIssue
from squad.ci.utils import task_id
from celery.utils.log import get_task_logger
from squad.mail import Message
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
            fetch.apply_async(args=(test_job.id,), task_id=task_id(test_job))


@celery.task
def fetch(job_id):
    logger.info("fetching %s" % job_id)
    try:
        testjob = TestJob.objects.get(pk=job_id)
        if testjob.job_id:
            testjob.backend.fetch(testjob.id)
    except TestJob.DoesNotExist:
        return


@celery.task
def cancel(job_id):
    logger.info("canceling %s" % job_id)
    testjob = TestJob.objects.get(pk=job_id)
    testjob.cancel()


@celery.task(bind=True)
def submit(self, job_id):
    test_job = TestJob.objects.get(pk=job_id)
    if not test_job.submitted:
        try:
            test_job.backend.submit(test_job)
            test_job.failure = None
            test_job.save()
        except SubmissionIssue as issue:
            test_job.failure = str(issue)
            test_job.save()

            if issue.retry:
                raise self.retry(exc=issue, countdown=3600)  # retry in 1 hour

            logger.warning("submitting job %s to %s: %s" % (test_job.id, test_job.backend.name, str(issue)))


@celery.task(priority=8)
def postprocess_testjob(job_id, job_status):
    logger.info("postprocessing  %s" % job_id)
    testjob = TestJob.objects.get(pk=job_id)
    backend = testjob.backend
    backend.__postprocess_testjob__(testjob, job_status)


@celery.task(priority=9)
def postprocess_testjob_subtasks(plugin_name, job_id, job_status):
    logger.info("postprocessing with subtasks %s" % job_id)
    plugin = get_plugin_instance(plugin_name)
    plugin.extra_args["job_status"] = job_status
    testjob = TestJob.objects.get(pk=job_id)
    try:
        plugin.postprocess_testjob(testjob)
    except Exception as e:
        logger.error("Plugin postprocessing error: " + str(e) + "\n" + traceback.format_exc())


@celery.task(priority=10)
def update_testjob_status(job_id, job_status):
    logger.info("updating testjob status %s" % job_id)
    if TestJob.sub_subtasks_count(job_id):
        testjob = TestJob.objects.get(pk=job_id)
        testjob.update_statuses(job_status)


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
        'squad/ci/testjob_resubmit.txt.jinja2',
        context=context,
    )
    html_message = ''
    html_message = render_to_string(
        'squad/ci/testjob_resubmit.html.jinja2',
        context=context,
    )

    message = Message(subject, text_message, sender, emails)
    if test_job.target.html_mail:
        message.attach_alternative(html_message, "text/html")
    message.send()
