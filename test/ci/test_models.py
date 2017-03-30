from django.test import TestCase


from squad.core import models as core_models


from squad.ci import models
from squad.ci.backend.null import Backend


class BackendTest(TestCase):

    def test_basics(self):
        models.Backend(
            url='http://example.com',
            username='foobar',
            token='mypassword'
        )

    def test_implementation(self):
        backend = models.Backend()
        impl = backend.get_implementation()
        self.assertIsInstance(impl, Backend)


class TestJobTest(TestCase):

    def test_basics(self):
        group = core_models.Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
        backend = models.Backend.objects.create(
            url='http://example.com',
            username='foobar',
            token='mypassword',
        )
        testjob = models.TestJob.objects.create(
            target=project,
            build='1',
            environment='myenv',
            backend=backend,
        )
        self.assertIsNone(testjob.job_id)
