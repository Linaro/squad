import logging
import re
import requests
import subprocess
from urllib.parse import urlparse


from django.conf import settings


from squad.core.models import ProjectStatus
from squad.core.plugins import Plugin as BasePlugin
from squad.frontend.templatetags.squad import build_url as __build_url__


logger = logging.getLogger()
DEFAULT_SSH_PORT = '29418'
DEFAULT_SSH_OPTIONS = ['-o', 'UserKnownHostsFile=/dev/null', '-o', 'StrictHostKeyChecking=no', '-o', 'LogLevel=ERROR']


def build_url(build):
    return settings.BASE_URL + __build_url__(build)


class Plugin(BasePlugin):

    @staticmethod
    def __message__(build, finished=False, extra_message=None):
        message = "Build {created_or_finished}: {build_version} ({build_url})"

        context = {
            'created_or_finished': 'finished' if finished else 'created',
            'build_version': build.version,
            'build_url': build_url(build),
        }

        if build.patch_baseline:
            message += "\nBaseline: {baseline_version} ({baseline_url})"
            context['baseline_version'] = build.patch_baseline.version
            context['baseline_url'] = build_url(build.patch_baseline)

        if extra_message:
            message += "\n" + extra_message

        return message.format(**context)

    @staticmethod
    def __gerrit_post__(build, payload):
        patch_source = build.patch_source
        parsed_url = urlparse(patch_source.url)
        auth = requests.auth.HTTPBasicAuth(patch_source.username, patch_source.password)
        change_id, patchset = re.split(r'[:/,]', build.patch_id)

        url = '{scheme}://{host}/a/changes/{change_id}/revisions/{patchset}/review'.format(
            scheme=parsed_url.scheme,
            host=parsed_url.netloc,
            change_id=change_id,
            patchset=patchset,
        )
        result = requests.post(url, auth=auth, json=payload)
        if result.status_code != 200:
            logger.error('Gerrit post failed, %s returned %d' % (parsed_url.netloc, result.status_code))
            return False
        return True

    @staticmethod
    def __gerrit_ssh__(build, payload):
        patch_source = build.patch_source
        parsed_url = urlparse(patch_source.url)
        change_id, patchset = re.split(r'[:/,]', build.patch_id)

        cmd = 'gerrit review -m "{message}" {change_id},{patchset}'.format(
            message=payload['message'],
            change_id=change_id,
            patchset=patchset,
        )

        if payload.get('labels') and payload['labels'].get('Code-Review'):
            cmd += ' --code-review %s' % (payload['labels']['Code-Review'])

        ssh = ['ssh']
        ssh += DEFAULT_SSH_OPTIONS
        ssh += ['-p', DEFAULT_SSH_PORT, '%s@%s' % (patch_source.username, parsed_url.netloc)]
        ssh += [cmd]
        try:
            result = subprocess.run(ssh, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            logger.error('Failed do login to %s: %s' % (parsed_url.netloc, str(e)))
            return False

        if len(result.stdout) > 0 or len(result.stderr) > 0:
            logger.error('Failed to submit review through ssh: %s' % (result.stdout + result.stderr))
            return False
        return True

    def __gerrit_request__(self, build, payload):
        regex = r'.+[:,].+'
        if re.match(regex, build.patch_id) is None:
            logger.warning('patch_id "%s" for build "%s" failed to match "%s"' % (build.patch_id, build.id, regex))
            return False

        if build.patch_source.url.startswith('ssh'):
            return Plugin.__gerrit_ssh__(build, payload)
        else:
            return Plugin.__gerrit_post__(build, payload)

    def notify_patch_build_created(self, build):
        data = {
            'message': Plugin.__message__(build),
        }
        return self.__gerrit_request__(build, data)

    def notify_patch_build_finished(self, build):
        down_vote = False
        try:
            if build.status.tests_fail == 0:
                message = "All tests passed"
            else:
                message = "Some tests failed (%d)" % build.status.tests_fail
                down_vote = True
        except ProjectStatus.DoesNotExist:
            logger.error('ProjectStatus for build %s/%s does not exist' % (build.project.slug, build.version))
            message = "An error occurred"

        data = {
            'message': Plugin.__message__(build, finished=True, extra_message=message),
        }

        if down_vote:
            data['labels'] = {'Code-Review': ' -1'}

        return self.__gerrit_request__(build, data)
