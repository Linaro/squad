from django.test import TestCase
from django.core.exceptions import ValidationError
from unittest.mock import patch


from squad.core.models import Group, PatchSource
from squad.plugins import gerrit


class FakeObject():
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
            implementation='gerrit'
        )
        self.ssh_patch_source = PatchSource.objects.create(
            name='ssh-gerrit',
            url='ssh://the.host',
            username='theuser',
            implementation='gerrit'
        )

        self.build1 = self.project.builds.create(version='1', patch_source=self.http_patch_source, patch_id='1,1')
        self.build2 = self.project.builds.create(version='2', patch_source=self.ssh_patch_source, patch_id='1,1')
        self.build3 = self.project.builds.create(version='3', patch_source=self.ssh_patch_source, patch_id=':')

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
    def test_http_notify_patch_build_finished(self):
        plugin = self.build1.patch_source.get_implementation()
        self.assertTrue(plugin.notify_patch_build_finished(self.build1))
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
