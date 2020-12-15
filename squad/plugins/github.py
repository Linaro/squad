import re
import requests
from django.conf import settings
from squad.core.models import ProjectStatus
from squad.core.plugins import Plugin as BasePlugin
from squad.frontend.templatetags.squad import project_url


def build_url(build):
    return settings.BASE_URL + project_url(build)


class Plugin(BasePlugin):

    @staticmethod
    def __github_post__(build, endpoint, payload):
        api_url = build.patch_source.url
        api_token = build.patch_source.token
        owner, repository, commit = re.split(r'[:/]', build.patch_id)

        headers = {
            "Authorization": "token %s" % api_token,
        }

        url = api_url + endpoint.format(
            owner=owner,
            repository=repository,
            commit=commit
        )
        return requests.post(url, headers=headers, json=payload)

    def notify_patch_build_created(self, build):
        payload = {
            "state": "pending",
            "target_url": build_url(build),
            "description": "This build is being tested",
            "context": "continuous-integration/squad"
        }
        endpoint = '/repos/{owner}/{repository}/statuses/{commit}'
        return Plugin.__github_post__(build, endpoint, payload)

    @staticmethod
    def __get_finished_state__(build):
        try:
            if (build.status.tests_fail == 0):
                return ("success", "All tests passed")
            else:
                return ("failure", "Some tests failed")
        except ProjectStatus.DoesNotExist:
            return ("error", "An error occurred")

    def notify_patch_build_finished(self, build):
        state, description = self.__get_finished_state__(build)
        payload = {
            "state": state,
            "target_url": build_url(build),
            "description": description,
            "context": "continuous-integration/squad"
        }
        endpoint = '/repos/{owner}/{repository}/statuses/{commit}'
        return Plugin.__github_post__(build, endpoint, payload)

    def get_url(self, build):
        api_url = build.patch_source.url
        owner, repository, commit = re.split(r'[:/]', build.patch_id)

        return "{api_url}/{owner}/{repository}/commit/{commit}".format(
            api_url=api_url,
            owner=owner,
            repository=repository,
            commit=commit
        )
