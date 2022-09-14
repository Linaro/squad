import random
import time
from squad.ci.models import TestJob
from squad.ci.tasks import fetch


description = "Fake"

TESTS = ("test1", "test2", "foo/test1", "foo/test2", "bar/test1", "bar/test2")
METRICS = ("metric1", "metric2", "foobenchmarks/metric1", "barbenchmarks/metric1")


class Backend(object):

    def __init__(self, data):
        self.data = data

    def submit(self, test_job):
        return [str(test_job.id)]

    def resubmit(self, test_job):
        count = test_job.resubmitted_count + 1
        new_jobid = '%s.%d' % (test_job.job_id, count)
        new_job = TestJob.objects.create(
            backend=self.data,
            testrun=test_job.testrun,
            target=test_job.target,
            target_build=test_job.target_build,
            environment=test_job.environment,
            submitted=True,
            job_id=new_jobid,
            resubmitted_count=count,
            definition=test_job.definition,
            parent_job=test_job
        )
        return new_job

    def fetch(self, test_job):
        status = 'Finished'
        completed = (random.randint(1, 20) <= 16)  # 80% success rate
        metadata = {"job_id": str(test_job.id), "foo": "bar"}
        tests = {test: (random.randint(1, 10) <= 8) and "pass" or 'fail' for test in TESTS}
        metrics = {metric: random.random() for metric in METRICS}
        logs = "a fake log file\ndate: " + time.strftime('%c') + "\n"
        return (status, completed, metadata, tests, metrics, logs)

    def listen(self):
        max_id = 0
        while True:
            time.sleep(random.randint(1, 5))
            jobs = self.data.test_jobs.filter(
                submitted=True,
                fetched=False,
                id__gt=max_id,
            ).order_by('id')
            for job in jobs:
                fetch.apply_async(args=[job.id])
                max_id = job.id

    def job_url(self, test_job):
        return 'https://example.com/job/%s' % test_job.job_id

    def cancel(self, test_job):
        return True

    def check_job_definition(self, definition):
        return True
