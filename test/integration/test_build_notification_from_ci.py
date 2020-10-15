from django.test import TestCase
from unittest.mock import patch


from squad.core.models import Group
from squad.ci.models import Backend


job_status = 'Finished'
completed = True
metadata = {'foo': 'bar'}
tests = {'test1': 'pass'}
metrics = {'metric1': {"value": 1, "unit": ""}}
logs = "hello world\nfinished\n"


class BuildNotificationFromCI(TestCase):

    @patch('squad.core.tasks.maybe_notify_project_status')
    @patch('squad.ci.backend.null.Backend.job_url', return_value="http://example.com/123")
    @patch('squad.ci.backend.null.Backend.fetch')
    def test_fetch_triggers_notification(self, fetch, job_url, notify):
        fetch.return_value = (job_status, completed, metadata, tests, metrics, logs)

        group = Group.objects.create(slug='mygroup')
        project = group.projects.create(slug='myproject')
        project.subscriptions.create(email='foo@example.com')
        build = project.builds.create(version='1')

        backend = Backend.objects.create(
            url='http://example.com',
            username='foobar',
            token='mypassword',
        )
        testjob = backend.test_jobs.create(
            target=project,
            target_build=build,
            job_id='123',
            environment='myenv',
        )
        backend.fetch(testjob.id)
        status = build.status
        status.refresh_from_db()
        notify.delay.assert_called_with(status.id)
        self.assertTrue(status.finished)
