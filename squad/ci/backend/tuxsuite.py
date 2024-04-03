import base64
import hashlib
import logging
import re
import requests
import yaml
import json

from requests.adapters import HTTPAdapter, Retry
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
from squad.core.models import TestRun


logger = logging.getLogger('squad.ci.backend.tuxsuite')


description = "TuxSuite"


requests_session = None


class Backend(BaseBackend):
    def has_resubmit(self):
        return False

    def has_cancel(self):
        return True

    @staticmethod
    def get_session():
        global requests_session
        if requests_session is None:
            retry_strategy = Retry(
                total=5,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504])
            adapter = HTTPAdapter(max_retries=retry_strategy)
            requests_session = requests.Session()
            requests_session.mount('http://', adapter)
            requests_session.mount('https://', adapter)
        return requests_session

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

        The leading string determines the type of the tuxsuite object:
        - BUILD
        - OEBUILD
        - TEST

        """

        regex = r'^(OEBUILD|BUILD|TEST):([0-9a-z_\-.]+@[0-9a-z_\-.]+)#([a-zA-Z0-9]+)$'
        matches = re.findall(regex, job_id)
        if len(matches) == 0:
            raise FetchIssue(f'Job id "{job_id}" does not match "{regex}"')

        # The regex below is supposed to find only one match
        return matches[0]

    def generate_job_id(self, result_type, result):
        """
            The job id for TuxSuite results is generated using 3 pieces of info:
            1. If it's either "BUILD", "OEBUILD" or "TEST" result;
            2. The TuxSuite project. Ex: "linaro/anders"
            3. The ksuid of the object. Ex: "1yPYGaOEPNwr2pfqBgONY43zORp"

            A couple examples for job_id are:
            - BUILD:linaro@anders#1yPYGaOEPNwr2pCqBgONY43zORq
            - OEBUILD:linaro@lkft#2Wetiz7Qs0TbtfPgPT7hUObWqDK
            - TEST:arm@bob#1yPYGaOEPNwr2pCqBgONY43zORp

            Then it's up to SQUAD's TuxSuite backend to parse the job_id
            and fetch results properly.
        """
        _type = result_type.upper()
        project = result["project"].replace("/", "@")
        uid = result["uid"]
        return f"{_type}:{project}#{uid}"

    def fetch_url(self, *urlbits):
        url = reduce(urljoin, urlbits)

        try:
            response = Backend.get_session().request("GET", url)
        except Exception as e:
            raise TemporaryFetchIssue(f"Can't retrieve from {url}: {e}")

        return response

    def fetch_from_results_input(self, test_job):
        try:
            return json.loads(test_job.input)
        except Exception as e:
            logger.error(f"Can't parse results from job's input: {e}")

        return None

    def set_build_name(self, test_job, job_url, results, metadata, settings):
        """
        Tuxsuite allows plans with builds and tests within.
        Some of these plans also support "special tests", which are
        kind a sanity test to run before spinning a heavy load of tests.

        Here's the default plan hierarchy:
          - build -> tests

        Now with sanity tests in between:
          - build -> sanity tests -> tests

        SQUAD needs to get to the build level in
        order to retrieve the build object and finally retrieve
        its build name attribute
        """

        build_id = results['waiting_for']
        if build_id is None or build_id.startswith('OEBUILD'):
            return

        items = build_id.split('#')
        if len(items) == 2:
            _type = items[0]
            _id = items[1]
        else:
            _type = "BUILD"
            _id = items[0]

        test_id = results['uid']

        try:
            # Check if the target build or sanity test is fetched
            job_id = self.generate_job_id(_type.lower(), results)
            job_id = job_id.replace(test_id, _id)

            candidate = TestRun.objects.get(
                build=test_job.target_build,
                job_id=job_id
            )

            build_name = candidate.metadata.get('build_name')
            if build_name:
                metadata['build_name'] = build_name
                return

        except TestRun.DoesNotExist:
            pass

        # It is a sanity test, an extra request is needed to get build id
        if _type == 'TEST':
            follow_test_url = job_url.replace(test_id, _id)
            test_json = self.fetch_url(follow_test_url).json()
            build_id = test_json.get('waiting_for')

        build_id = build_id.replace('BUILD#', '')
        build_url = job_url.replace(test_id, build_id).replace('/tests/', '/builds/')

        build_metadata = self.fetch_url(build_url).json()

        build_metadata_keys = settings.get('TEST_BUILD_METADATA_KEYS', [])
        metadata.update({k: build_metadata.get(k) for k in build_metadata_keys})

        if 'toolchain' in build_metadata_keys and 'kconfig' in build_metadata_keys and metadata['build_name'] in [None, '']:
            metadata['build_name'] = self.generate_test_name(build_metadata)

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
        metadata['job_id'] = test_job.job_id
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

    def parse_oebuild_results(self, test_job, job_url, results, settings):
        required_keys = ['download_url', 'result']
        self.__check_required_keys__(required_keys, results)

        # Make metadata
        metadata_keys = settings.get('OEBUILD_METADATA_KEYS', [])
        metadata = {k: results.get(k) for k in metadata_keys}
        metadata['job_url'] = job_url
        metadata['job_id'] = test_job.job_id

        sources = results.get('sources')
        if sources:
            metadata['sources'] = sources

        # Create tests and metrics
        tests = {}
        metrics = {}
        completed = True
        status = 'Complete'
        tests['build/build'] = 'pass' if results['result'] == 'pass' else 'fail'
        logs = self.fetch_url(results['download_url'], 'build.log').text

        return status, completed, metadata, tests, metrics, logs

    def update_metadata_from_file(self, results, metadata):
        if "download_url" in results:
            download_url = results["download_url"]
            try:
                test_metadata_response = self.fetch_url(download_url + '/' + 'metadata.json')
                # If fetching the metadata file did not error, decode it as json
                if test_metadata_response.ok:
                    metadata.update(test_metadata_response.json())
            except TemporaryFetchIssue:
                pass

    def parse_test_results(self, test_job, job_url, results, settings):
        status = 'Complete'
        completed = True
        tests = {}
        metrics = {}
        logs = ''

        # Pick up some metadata from results
        metadata_keys = settings.get('TEST_METADATA_KEYS', [])
        metadata = {k: results.get(k) for k in metadata_keys}

        # Add extra metadata from metadata file if it exists
        self.update_metadata_from_file(results=results, metadata=metadata)

        metadata['job_url'] = job_url
        metadata['job_id'] = test_job.job_id

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

        # Follow up the chain and retrieve build name
        self.set_build_name(test_job, job_url, results, metadata, settings)

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
        env = status.get("target_arch") or status.get("device") or environment
        job_id = self.generate_job_id(kind, status)
        try:
            # Tuxsuite's job id DO NOT repeat, like ever
            testjob = TestJob.objects.get(job_id=job_id, target_build=build, environment=env)
        except TestJob.DoesNotExist:
            testjob = TestJob.objects.create(
                backend=backend,
                target=build.project,
                target_build=build,
                environment=env,
                submitted=True,
                job_id=job_id
            )

        # Saves the input so it can be processed by the queue
        testjob.input = json.dumps(status)

        return testjob
