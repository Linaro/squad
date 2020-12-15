from django.test import TestCase
from django.core.exceptions import ValidationError
from unittest.mock import patch


from squad.core.models import Group, PatchSource
from squad.plugins import gerrit

plugins_settings = """
plugins:
  gerrit:
    build_finished:
      success:
        My-Custom-Label: "+1"
      error:
        Custom-Code-Review: "-1"
        Other-Label: "-2"
"""

response_json_text = """)]}'
{
  "id": "TF-A%2Ftf-a-tests~master~I115a921c777b7932523d2dff8e8e03377d87bb78",
  "project": "foo/bar",
  "branch": "master",
  "topic": "af/bf",
  "hashtags": [],
  "change_id": "I115a921c777b7932523d2dff8e8e03377d87bb78",
  "subject": "af: bf",
  "status": "NEW",
  "created": "2020-12-07 18:17:44.000000000",
  "updated": "2020-12-10 09:18:10.000000000",
  "submit_type": "MERGE_ALWAYS",
  "mergeable": true,
  "insertions": 27,
  "deletions": 4,
  "total_comment_count": 6,
  "unresolved_comment_count": 3,
  "has_review_started": true,
  "_number": 1,
  "owner": {
    "_account_id": 1000105
  },
  "requirements": []
}
"""


class FakeObject():
    text = response_json_text
    pass


class FakeSubprocess():
    __last_cmd__ = None
    PIPE = 0

    class CalledProcessError(BaseException):
        def __str__(self):
            return 'Could not establish connection to host'

    @staticmethod
    def run(cmd, stdout=0, stderr=0):
        FakeSubprocess.__last_cmd__ = ' '.join(cmd)
        gerrit_cmd = 'gerrit review'
        options = ' '.join(gerrit.DEFAULT_SSH_OPTIONS)
        port = gerrit.DEFAULT_SSH_PORT
        if 'ssh %s -p %s theuser@the.host' % (options, port) != ' '.join(cmd[0:10]) \
                or not cmd[10].startswith(gerrit_cmd):
            raise FakeSubprocess.CalledProcessError()

        obj = FakeObject()
        obj.stdout = ""
        obj.stderr = ""
        return obj

    @staticmethod
    def given_cmd():
        return FakeSubprocess.__last_cmd__


class FakeRequests():
    __last_json__ = None

    class auth():
        class HTTPBasicAuth():
            def __init__(self, user, password):
                self.user = user
                self.password = password

    @staticmethod
    def post(url, auth=None, json=None):
        FakeRequests.__last_json__ = json
        result = FakeObject()
        result.status_code = 200
        user = auth.user
        password = auth.password
        if 'https://the.host' not in url or [user, password] != ['theuser', '1234'] or json['message'] is None:
            result.status_code = 400
        return result

    @staticmethod
    def get(url, auth=None, json=None):
        FakeRequests.__last_json__ = json
        result = FakeObject()
        result.status_code = 200
        user = auth.user
        password = auth.password
        if 'https://the.host' not in url or [user, password] != ['theuser', '1234']:
            result.status_code = 400
        return result

    @staticmethod
    def given_json():
        return FakeRequests.__last_json__


class GerritPluginTest(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        self.project = group.projects.create(slug='myproject')
        self.http_patch_source = PatchSource.objects.create(
            name='http-gerrit',
            url='https://the.host',
            username='theuser',
            password='1234',
            implementation='gerrit',
            token=''
        )
        self.ssh_patch_source = PatchSource.objects.create(
            name='ssh-gerrit',
            url='ssh://the.host',
            username='theuser',
            password='',
            implementation='gerrit',
            token=''
        )

        self.build1 = self.project.builds.create(version='1', patch_source=self.http_patch_source, patch_id='1,1')
        self.build2 = self.project.builds.create(version='2', patch_source=self.ssh_patch_source, patch_id='1,1')
        self.build3 = self.project.builds.create(version='3', patch_source=self.ssh_patch_source, patch_id=':')
        self.build4 = self.project.builds.create(version='4', patch_source=self.http_patch_source, patch_id='1/1')

    def test_basic_validation(self):
        validation_error = False
        try:
            self.http_patch_source.full_clean()
            self.ssh_patch_source.full_clean()
        except ValidationError:
            validation_error = True
        self.assertFalse(validation_error)

    @patch('squad.plugins.gerrit.requests', FakeRequests)
    def test_http(self):
        plugin = self.build1.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_created(self.build1))

    @patch('squad.plugins.gerrit.requests', FakeRequests)
    def test_http_notify_patch_build_created(self):
        plugin = self.build1.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_created(self.build1))
        self.assertIn('Build created', FakeRequests.given_json()['message'])

    @patch('squad.plugins.gerrit.requests', FakeRequests)
    def test_get_url(self):
        self.build1.patch_source.get_implementation()
        gerrit_url = self.build1.patch_source.get_url(self.build1)
        self.assertEqual(gerrit_url, "https://the.host/c/foo/bar/+/1/1")

    @patch('squad.plugins.gerrit.requests', FakeRequests)
    def test_get_url_ssh(self):
        self.build2.patch_source.get_implementation()
        gerrit_url = self.build2.patch_source.get_url(self.build2)
        self.assertEqual(gerrit_url, None)

    @patch('squad.plugins.gerrit.requests', FakeRequests)
    def test_http_notify_patch_build_finished(self):
        plugin = self.build1.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_finished(self.build1))
        self.assertIn('Build finished', FakeRequests.given_json()['message'])

    @patch('squad.plugins.gerrit.requests', FakeRequests)
    def test_http_notify_patch_build4_finished(self):
        plugin = self.build4.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_finished(self.build4))
        self.assertIn('Build finished', FakeRequests.given_json()['message'])

    @patch('squad.plugins.gerrit.requests', FakeRequests)
    def test_http_notify_patch_build_finished_with_failures(self):
        self.build1.status.tests_fail = 1
        self.build1.status.save()
        plugin = self.build1.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_finished(self.build1))
        self.assertIn('Build finished', FakeRequests.given_json()['message'])
        self.assertIn('Some tests failed (1)', FakeRequests.given_json()['message'])

    @patch('squad.plugins.gerrit.subprocess', FakeSubprocess)
    def test_ssh(self):
        plugin = self.build2.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_created(self.build2))

    @patch('squad.plugins.gerrit.subprocess', FakeSubprocess)
    def test_ssh_failed_login(self):
        self.build2.patch_source.username = 'wronguser'
        plugin = self.build2.patch_source.get_implementation()
        self.assertFalse(plugin.notify_patch_build_created(self.build2))

    @patch('squad.plugins.gerrit.subprocess', FakeSubprocess)
    def test_ssh_notify_patch_build_created(self):
        plugin = self.build2.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_created(self.build2))
        self.assertIn('Build created', FakeSubprocess.given_cmd())

    @patch('squad.plugins.gerrit.subprocess', FakeSubprocess)
    def test_ssh_notify_patch_build_finished(self):
        plugin = self.build2.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_finished(self.build2))
        self.assertIn('Build finished', FakeSubprocess.given_cmd())

    @patch('squad.plugins.gerrit.subprocess', FakeSubprocess)
    def test_ssh_notify_patch_build_finished_with_failures(self):
        self.build2.status.tests_fail = 1
        self.build2.status.save()
        plugin = self.build2.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_finished(self.build2))
        self.assertIn('Build finished', FakeSubprocess.given_cmd())
        self.assertIn('Some tests failed (1)', FakeSubprocess.given_cmd())

    def test_malformed_patch_id(self):
        plugin = self.build3.patch_source.get_implementation()
        self.assertFalse(plugin.notify_patch_build_created(self.build3))

    @patch('squad.plugins.gerrit.subprocess', FakeSubprocess)
    def test_ssh_default_labels(self):
        self.build2.status.tests_fail = 1
        self.build2.status.save()
        plugin = self.build2.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_finished(self.build2))
        self.assertIn('--label code-review=-1', FakeSubprocess.given_cmd())

        self.build2.status.tests_fail = 0
        self.build2.status.save()
        plugin = self.build2.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_finished(self.build2))
        self.assertNotIn('--label code-review=+1', FakeSubprocess.given_cmd())

    @patch('squad.plugins.gerrit.subprocess', FakeSubprocess)
    def test_ssh_custom_labels(self):
        self.project.project_settings = plugins_settings
        self.project.save()

        self.build2.status.tests_fail = 1
        self.build2.status.save()
        plugin = self.build2.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_finished(self.build2))
        self.assertIn('--label custom-code-review=-1', FakeSubprocess.given_cmd())
        self.assertIn('--label other-label=-2', FakeSubprocess.given_cmd())
        self.assertNotIn('--label my-custom-label=+1', FakeSubprocess.given_cmd())

        self.build2.status.tests_fail = 0
        self.build2.status.save()
        plugin = self.build2.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_finished(self.build2))
        self.assertIn('--label my-custom-label=+1', FakeSubprocess.given_cmd())
        self.assertNotIn('--label custom-code-review=-1', FakeSubprocess.given_cmd())

    @patch('squad.plugins.gerrit.requests', FakeRequests)
    def test_rest_default_labels(self):
        self.build1.status.tests_fail = 1
        self.build1.status.save()
        plugin = self.build1.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_finished(self.build1))
        labels = FakeRequests.given_json()['labels']
        self.assertEqual('-1', labels.get('Code-Review'))

        self.build1.status.tests_fail = 0
        self.build1.status.save()
        plugin = self.build1.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_finished(self.build1))
        labels = FakeRequests.given_json()['labels']
        self.assertEqual(None, labels.get('Code-Review'))

    @patch('squad.plugins.gerrit.requests', FakeRequests)
    def test_rest_custom_labels(self):
        self.project.project_settings = plugins_settings
        self.project.save()

        self.build1.status.tests_fail = 1
        self.build1.status.save()
        plugin = self.build1.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_finished(self.build1))
        labels = FakeRequests.given_json()['labels']
        self.assertEqual('-1', labels.get('Custom-Code-Review'))
        self.assertEqual('-2', labels.get('Other-Label'))
        self.assertEqual(None, labels.get('My-Custom-Label'))

        self.build1.status.tests_fail = 0
        self.build1.status.save()
        plugin = self.build1.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_finished(self.build1))
        labels = FakeRequests.given_json()['labels']
        self.assertEqual('+1', labels.get('My-Custom-Label'))
        self.assertEqual(None, labels.get('Custom-Code-Review'))
