import base64
import hashlib
import logging
import re
import requests
import yaml
import json

from functools import reduce
from urllib.parse import urljoin

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import (
    hashes,
    serialization,
)

from squad.ci.backend.null import Backend as BaseBackend
from squad.ci.exceptions import FetchIssue, TemporaryFetchIssue
from squad.ci.models import TestJob


logger = logging.getLogger('squad.ci.backend.tuxsuite')


description = "TuxSuite"


class Backend(BaseBackend):

    """
    TuxSuite backend is intended for processing data coming from TuxTest
    """

    def generate_test_name(self, results):
        """
        Generates a name based on toolchain and config. Here are few examples:

        1) toolchain: gcc-9, kconfig: ['defconfig']
           -> returns 'gcc-9-defconfig'

        2) toolchain: gcc-9, kconfig: ['defconfig', 'CONFIG_LALA=y']
           -> returns 'gcc-9-defconfig-6bbfee93'
                                       -> hashlib.sha1('CONFIG_LALA=y')[0:8]

        3) toolchain: gcc-9, kconfig: ['defconfig', 'CONFIG_LALA=y', 'https://some.com/kconfig']
           -> returns 'gcc-9-defconfig-12345678'
                                      -> hashlib.sha1(
                                             sorted(
                                                 'CONFIG_LALA=y',
                                                 'https://some.com/kconfig',
                                             )
                                         )
        """
        name = results['toolchain']

        # If there are any configuration coming from a URL,
        # fetch it then merge all in a dictionary for later
        # hash it and make up the name
        configs = results['kconfig']
        name += f'-{configs[0]}'
        configs = configs[1:]

        if len(configs):
            sha = hashlib.sha1()

            for config in configs:
                sha.update(f'{config}'.encode())

            name += '-' + sha.hexdigest()[0:8]

        return name

    def parse_job_id(self, job_id):
        """
        Parsing the job id means getting back specific TuxSuite information
        from job_id. Ex:

        Given a job_id = "BUILD:linaro@anders#1yPYGaOEPNwr2pCqBgONY43zORq",
        the return value should be a tuple like

        ('BUILD', 'linaro@anders', '1yPYGaOEPNwr2pCqBgONY43zORq')

        """

        regex = r'^(BUILD|TEST):([0-9a-z_\-]+@[0-9a-z_\-]+)#([a-zA-Z0-9]+)$'
        matches = re.findall(regex, job_id)
        if len(matches) == 0:
            raise FetchIssue(f'Job id "{job_id}" does not match "{regex}"')

        # The regex below is supposed to find only one match
        return matches[0]

    def generate_job_id(self, result_type, result):
        """
            The job id for TuxSuite results is generated using 3 pieces of info:
            1. If it's either "BUILD" or "TEST" result;
            2. The TuxSuite project. Ex: "linaro/anders"
            3. The ksuid of the object. Ex: "1yPYGaOEPNwr2pfqBgONY43zORp"

            A couple examples for job_id are:
            - BUILD:linaro@anders#1yPYGaOEPNwr2pCqBgONY43zORq
            - TEST:arm@bob#1yPYGaOEPNwr2pCqBgONY43zORp

            Then it's up to SQUAD's TuxSuite backend to parse the job_id
            and fetch results properly.
        """
        _type = "TEST" if result_type == "test" else "BUILD"
        project = result["project"].replace("/", "@")
        uid = result["uid"]
        return f"{_type}:{project}#{uid}"

    def fetch_url(self, *urlbits):
        url = reduce(urljoin, urlbits)

        try:
            response = requests.get(url)
        except Exception as e:
            raise TemporaryFetchIssue(f"Can't retrieve from {url}: {e}")

        return response

    def fetch_from_results_input(self, test_job):
        try:
            return json.loads(test_job.input)
        except Exception as e:
            logger.error(f"Can't parse results from job's input: {e}")

        return None

    def parse_build_results(self, test_job, job_url, results, settings):
        required_keys = ['build_status', 'warnings_count', 'download_url', 'retry']
        self.__check_required_keys__(required_keys, results)

        # Generate generic test/metric name
        test_name = results.get('build_name') or self.generate_test_name(results)
        test_job.name = test_name

        build_status = results['build_status']
        if build_status == 'error' and results['retry'] < 2:
            # SQUAD should retry fetching the build until retry == 2
            raise TemporaryFetchIssue(results.get('status_message', 'TuxSuite Error'))

        # Make metadata
        metadata_keys = settings.get('BUILD_METADATA_KEYS', [])
        metadata = {k: results.get(k) for k in metadata_keys}
        metadata['job_url'] = job_url
        metadata['config'] = urljoin(results.get('download_url') + '/', 'config')
        metadata['build_name'] = test_name

        # Create tests and metrics
        tests = {}
        metrics = {}

        completed = True
        if results['retry'] >= 2:
            # This indicates that TuxSuite gave up trying to work on this build
            status = 'Incomplete'
            tests[f'build/{test_name}'] = 'skip'
            logs = ''
        else:
            status = 'Complete'
            tests[f'build/{test_name}'] = build_status
            metrics[f'build/{test_name}-warnings'] = results['warnings_count']
            logs = self.fetch_url(results['download_url'], 'build.log').text

            try:
                metrics[f'build/{test_name}-duration'] = results['tuxmake_metadata']['results']['duration']['build']
            except KeyError:
                raise FetchIssue('Missing duration from build results')

        return status, completed, metadata, tests, metrics, logs

    def parse_test_results(self, test_job, job_url, results, settings):
        status = 'Complete'
        completed = True
        tests = {}
        metrics = {}
        logs = ''

        # Pick up some metadata from results
        metadata_keys = settings.get('TEST_METADATA_KEYS', [])
        metadata = {k: results.get(k) for k in metadata_keys}
        metadata['job_url'] = job_url

        # Set job name
        try:
            results['tests'].remove('boot')
        except ValueError:
            pass
        test_job.name = ','.join(results['tests'])

        if results['results'] == {}:
            test_job.failure = 'build failed'
            return status, completed, metadata, tests, metrics, logs

        # Fetch results even if the job fails, but has results
        if results['result'] == 'fail':
            test_job.failure = str(results['results'])

        elif results['result'] == 'error':
            test_job.failure = 'tuxsuite infrastructure error'
            return 'Incomplete', completed, metadata, tests, metrics, logs

        # If boot result is unkown, a retry is needed, otherwise, it either passed or failed
        if 'unknown' == results['results']['boot']:
            return None

        # Retrieve TuxRun log
        logs = self.fetch_url(job_url + '/', 'logs?format=txt').text

        # Fetch more metadata if available
        if results['waiting_for'] is not None:
            _, _, test_id = self.parse_job_id(test_job.job_id)
            build_id = results['waiting_for']
            build_url = job_url.replace(test_id, build_id).replace('tests', 'builds')

            # TODO: check if we can save a few seconds by querying a testjob that
            # already contains build results
            build_metadata = self.fetch_url(build_url).json()

            build_metadata_keys = settings.get('TEST_BUILD_METADATA_KEYS', [])
            metadata.update({k: build_metadata.get(k) for k in build_metadata_keys})

            if 'toolchain' in build_metadata_keys and 'kconfig' in build_metadata_keys and metadata['build_name'] in [None, '']:
                metadata['build_name'] = self.generate_test_name(build_metadata)

        # Create a boot test
        boot_test_name = 'boot/' + (metadata.get('build_name') or 'boot')
        tests[boot_test_name] = results['results']['boot']

        # Really fetch test results
        tests_results = self.fetch_url(job_url + '/', 'results').json()
        if tests_results.get('error', None) is None:
            for suite, suite_tests in tests_results.items():
                if suite == 'lava':
                    continue

                suite_name = re.sub(r'^[0-9]+_', '', suite)
                for name, test_data in suite_tests.items():
                    test_name = f'{suite_name}/{name}'
                    result = test_data['result']

                    # TODO: Log lines are off coming from TuxRun/LAVA
                    # test_log = self.get_test_log(log_dict, test)
                    tests[test_name] = result

        return status, completed, metadata, tests, metrics, logs

    def fetch(self, test_job):
        url = self.job_url(test_job)
        if test_job.input:
            results = self.fetch_from_results_input(test_job)
            test_job.input = None
        else:
            results = self.fetch_url(url).json()

        if results.get('state') != 'finished':
            return None

        settings = self.__resolve_settings__(test_job)

        result_type = self.parse_job_id(test_job.job_id)[0]
        parse_results = getattr(self, f'parse_{result_type.lower()}_results')
        return parse_results(test_job, url, results, settings)

    def job_url(self, test_job):
        result_type, tux_project, tux_uid = self.parse_job_id(test_job.job_id)
        tux_group, tux_user = tux_project.split('@')
        endpoint = f'groups/{tux_group}/projects/{tux_user}/{result_type.lower()}s/{tux_uid}'
        return urljoin(self.data.url, endpoint)

    def __check_required_keys__(self, required_keys, results):
        missing_keys = []
        for k in required_keys:
            if k not in results:
                missing_keys.append(k)

        if len(missing_keys):
            keys = ', '.join(missing_keys)
            results_json = json.dumps(results)
            raise FetchIssue(f'{keys} are required and missing from {results_json}')

    def __resolve_settings__(self, test_job):
        result_settings = self.settings
        if getattr(test_job, 'target', None) is not None \
                and test_job.target.project_settings is not None:
            ps = yaml.safe_load(test_job.target.project_settings) or {}
            result_settings.update(ps)
        return result_settings

    def cancel(self, testjob):
        result_type, tux_project, tux_uid = self.parse_job_id(testjob.job_id)
        tux_group, tux_user = tux_project.split('@')
        endpoint = f'groups/{tux_group}/projects/{tux_user}/{result_type.lower()}s/{tux_uid}/cancel'
        url = urljoin(self.data.url, endpoint)
        response = requests.post(url)
        return response.status_code == 200

    def supports_callbacks(self):
        return True

    def validate_callback(self, request, project):
        signature = request.headers.get("x-tux-payload-signature", None)
        if signature is None:
            raise Exception("tuxsuite request is missing signature headers")

        public_key = project.get_setting("TUXSUITE_PUBLIC_KEY")
        if public_key is None:
            raise Exception("missing tuxsuite public key for this project")

        payload = json.loads(request.body)
        signature = base64.urlsafe_b64decode(signature)
        key = serialization.load_ssh_public_key(public_key.encode("ascii"))
        key.verify(
            signature,
            payload.encode("utf-8"),
            ec.ECDSA(hashes.SHA256()),
        )

    def process_callback(self, json_payload, build, environment, backend):
        # The payload coming from Tuxsuite is formatted as bytes,
        # so after the first json.loads(request.body), the result
        # will still be a string containing the actual json document
        # We need to call json.loads() once more to get the actual
        # python dict containing all the information we need
        json_payload = json.loads(json_payload)
        if "kind" not in json_payload or "status" not in json_payload:
            raise Exception("`kind` and `status` are required in the payload")

        kind = json_payload["kind"]
        status = json_payload["status"]
        job_id = self.generate_job_id(kind, status)
        try:
            # Tuxsuite's job id DO NOT repeat, like ever
            testjob = TestJob.objects.get(job_id=job_id, target_build=build, environment=environment.slug)
        except TestJob.DoesNotExist:
            testjob = TestJob.objects.create(
                backend=backend,
                target=build.project,
                target_build=build,
                environment=environment.slug,
                submitted=True,
                job_id=job_id
            )

        # Saves the input so it can be processed by the queue
        testjob.input = json.dumps(status)

        return testjob
