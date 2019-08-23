from django.test import TestCase
from unittest.mock import patch, ANY


from squad.plugins.github import Plugin
from squad.core.models import Group, PatchSource


class GithubPluginTest(TestCase):

    def setUp(self):
        group = Group.objects.create(slug='mygroup')
        self.project = group.projects.create(slug='myproject', enabled_plugins_list='example')
        self.patch_source = PatchSource.objects.create(
            name='github',
            url='https://api.github.com',
            username='example',
            token='123456789',
        )
        self.build = self.project.builds.create(version='1', patch_source=self.patch_source, patch_id='foo/bar/deadbeef')
        self.github = Plugin()

    @patch('squad.plugins.github.requests')
    def test_github_post(self, requests):
        Plugin.__github_post__(self.build, '/test/{owner}/{repository}/{commit}', {"a": "b"})
        requests.post.assert_called_with(
            'https://api.github.com/test/foo/bar/deadbeef',
            headers={'Authorization': 'token 123456789'},
            json={"a": "b"},
        )

    @patch('squad.plugins.github.Plugin.__github_post__')
    def test_notify_patch_build_created(self, __github_post__):
        self.github.notify_patch_build_created(self.build)
        __github_post__.assert_called_with(self.build, "/repos/{owner}/{repository}/statuses/{commit}", ANY)

    @patch('squad.plugins.github.Plugin.__github_post__')
    def test_notify_patch_build_finished(self, __github_post__):
        self.github.notify_patch_build_finished(self.build)
        __github_post__.assert_called_with(self.build, "/repos/{owner}/{repository}/statuses/{commit}", ANY)

    @patch('squad.plugins.github.Plugin.__github_post__')
    def test_notify_patch_build_finished_no_failures(self, __github_post__):
        self.build.status.tests_pass = 1
        self.build.status.save()
        state, _ = self.github.__get_finished_state__(self.build)
        self.assertEqual("success", state)

    @patch('squad.plugins.github.Plugin.__github_post__')
    def test_notify_patch_build_finished_with_failures(self, __github_post__):
        self.build.status.tests_fail = 1
        self.build.status.save()
        state, _ = self.github.__get_finished_state__(self.build)
        self.assertEqual("failure", state)
