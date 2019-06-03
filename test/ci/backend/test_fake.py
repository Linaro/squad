from django.test import TestCase
from squad.core.models import Group, Project
from squad.ci.models import Backend, TestJob
from squad.ci.backend.fake import Backend as FakeBackend


class FakeBackendTest(TestCase):

    def setUp(self):
        self.backend = Backend.objects.create(
            url='http://example.com/',
            username='myuser',
            token='mypassword',
            implementation_type='fake',
        )
        self.group = Group.objects.create(
            name="group_foo"
        )
        self.project = Project.objects.create(
            name="project_foo",
            group=self.group,
        )

    def test_impl(self):
        self.assertIsInstance(self.backend.get_implementation(), FakeBackend)

    def test_submit(self):
        job = TestJob.objects.create(backend=self.backend, target=self.project)
        impl = FakeBackend(self.backend)
        jid = impl.submit(job)
        self.assertEqual([str(job.id)], jid)

    def test_resubmit(self):
        job = TestJob.objects.create(backend=self.backend, target=self.project, job_id='22')
        impl = FakeBackend(self.backend)
        new_job = impl.resubmit(job)
        self.assertIsInstance(new_job, TestJob)
        self.assertIsNot(job, new_job)
        self.assertEqual('22.1', new_job.job_id)
        self.assertEqual(job, new_job.parent_job)

    def test_resubmit_resubmitted(self):
        job = TestJob.objects.create(backend=self.backend, target=self.project, job_id='22.1')
        impl = FakeBackend(self.backend)
        new_job = impl.resubmit(job)
        self.assertEqual('22.1.1', new_job.job_id)

    def test_fetch(self):
        job = TestJob.objects.create(backend=self.backend, target=self.project)
        impl = FakeBackend(self.backend)
        (status, completed, metadata, tests, metrics, logs) = impl.fetch(job)
        self.assertIsInstance(status, str)
        self.assertIsInstance(completed, bool)
        self.assertIsInstance(metadata, dict)
        self.assertIsInstance(tests, dict)
        self.assertIsInstance(metrics, dict)
        self.assertIsInstance(logs, str)

    def test_job_url(self):
        job = TestJob(job_id='123')
        impl = FakeBackend(self.backend)
        self.assertIsInstance(impl.job_url(job), str)
