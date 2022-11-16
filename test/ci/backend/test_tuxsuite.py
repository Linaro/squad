import hashlib
import requests
import requests_mock
import json

from urllib.parse import urljoin
from django.test import TestCase

from squad.ci.backend.tuxsuite import Backend as TuxSuiteBackend
from squad.ci.exceptions import FetchIssue, TemporaryFetchIssue
from squad.ci.models import Backend
from squad.core.models import Group, Project


TUXSUITE_URL = 'http://testing.tuxsuite.com'


class TuxSuiteTest(TestCase):

    def setUp(self):
        self.backend = Backend.objects.create(
            url=TUXSUITE_URL,
            implementation_type='tuxsuite',
            backend_settings="""
                {
                    "BUILD_METADATA_KEYS": [
                        "build_status",
                        "download_url",
                        "git_describe",
                        "git_ref",
                        "git_repo",
                        "git_sha",
                        "git_short_log",
                        "kernel_version",
                        "kconfig",
                        "target_arch",
                        "toolchain",
                        "does_not_exist"
                    ],
                    "TEST_METADATA_KEYS": [
                        "does_not_exist"
                    ],
                    "TEST_BUILD_METADATA_KEYS": [
                        "build_name",
                        "kconfig",
                        "toolchain"
                    ],
                }
            """,
        )
        self.group = Group.objects.create(
            name="tuxgroup"
        )
        self.project = Project.objects.create(
            name="tuxprojext",
            group=self.group,
        )
        self.build = self.project.builds.create(version='tuxbuild')
        self.tuxsuite = TuxSuiteBackend(self.backend)

    def test_detect(self):
        impl = self.backend.get_implementation()
        self.assertIsInstance(impl, TuxSuiteBackend)

    def test_not_implemented(self):
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend)

        with self.assertRaises(NotImplementedError):
            self.tuxsuite.submit(testjob)

        with self.assertRaises(NotImplementedError):
            self.tuxsuite.resubmit(testjob)

        with self.assertRaises(NotImplementedError):
            self.tuxsuite.listen()

    def test_generate_test_name(self):
        results = {
            'toolchain': 'gcc-10',
            'kconfig': ['defconfig', 'CONFIG_DUMMY=1'],
        }

        sha = hashlib.sha1()
        for k in results['kconfig'][1:]:
            sha.update(k.encode())

        expected_name = results['toolchain'] + '-defconfig-' + sha.hexdigest()[0:8]
        self.assertEqual(expected_name, self.tuxsuite.generate_test_name(results))

    def test_parse_job_id(self):
        result = self.tuxsuite.parse_job_id('BUILD:linaro@anders#1yPYGaOEPNwr2pCqBgONY43zORq')
        self.assertEqual(('BUILD', 'linaro@anders', '1yPYGaOEPNwr2pCqBgONY43zORq'), result)

        result = self.tuxsuite.parse_job_id('TEST:linaro@anders#1yPYGaOEPNwr2pCqBgONY43zORq')
        self.assertEqual(('TEST', 'linaro@anders', '1yPYGaOEPNwr2pCqBgONY43zORq'), result)

        with self.assertRaises(FetchIssue):
            self.tuxsuite.parse_job_id('not-really-vallid')

        with self.assertRaises(FetchIssue):
            self.tuxsuite.parse_job_id('BLAH:linaro@anders#1yPYGaOEPNwr2pCqBgONY43zORq')

    def test_job_url(self):
        # Builds job url
        job_id = 'BUILD:linaro@anders#1yPYGaOEPNwr2pCqBgONY43zORq'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        endpoint = '/groups/linaro/projects/anders/builds/1yPYGaOEPNwr2pCqBgONY43zORq'
        expected = urljoin(TUXSUITE_URL, endpoint)
        self.assertEqual(expected, self.tuxsuite.job_url(testjob))

        # Tests job url
        job_id = 'TEST:linaro@anders#1yPYGaOEPNwr2pCqBgONY43zORq'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        endpoint = '/groups/linaro/projects/anders/tests/1yPYGaOEPNwr2pCqBgONY43zORq'
        expected = urljoin(TUXSUITE_URL, endpoint)
        self.assertEqual(expected, self.tuxsuite.job_url(testjob))

    def test_fetch_url(self):
        expected_logs = 'dummy build log'

        with requests_mock.Mocker() as fake_request:
            url = 'http://tuxbuild.com/build1/build.log'

            fake_request.get(url, text=expected_logs)
            result = self.tuxsuite.fetch_url(url)

        self.assertEqual(expected_logs, result.text)

    def test_fetch_url_faulty_url(self):
        with requests_mock.Mocker() as fake_request:
            url = 'http://tuxbuild.com/build1/build.log'
            fake_request.get(url, exc=requests.exceptions.ConnectTimeout)

            with self.assertRaises(TemporaryFetchIssue):
                self.tuxsuite.fetch_url(url)

    def test_fetch_build_results(self):
        job_id = 'BUILD:tuxgroup@tuxproject#123'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        build_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/builds/123')
        build_download_url = 'http://builds.tuxbuild.com/123'

        # Only fetch when finished
        with requests_mock.Mocker() as fake_request:
            fake_request.get(build_url, json={'state': 'running'})
            results = self.tuxsuite.fetch(testjob)
            self.assertEqual(None, results)

        build_logs = 'dummy build log'
        build_results = {
            'retry': 0,
            'state': 'finished',
            'build_status': 'pass',
            'build_name': 'tux-build',
            'git_repo': 'https://github.com/Linaro/linux-canaries.git',
            'git_ref': 'v5.9',
            'git_describe': 'v5.9',
            'git_sha': 'bbf5c979011a099af5dc76498918ed7df445635b',
            'git_short_log': 'bbf5c979011a ("Linux 5.9")',
            'kernel_version': '5.9.0',
            'kconfig': ['tinyconfig'],
            'target_arch': 'x86_64',
            'toolchain': 'gcc-10',
            'download_url': build_download_url,
            'provisioning_time': '2022-03-25T15:42:06.570362',
            'running_time': '2022-03-25T15:44:16.223590',
            'finished_time': '2022-03-25T15:46:56.095902',
            'warnings_count': '2',
            'tuxmake_metadata': {
                'results': {
                    'duration': {
                        'build': '42',
                    },
                },
            },
        }

        expected_metadata = {
            'job_url': build_url,
            'build_status': 'pass',
            'git_repo': 'https://github.com/Linaro/linux-canaries.git',
            'git_ref': 'v5.9',
            'git_describe': 'v5.9',
            'git_sha': 'bbf5c979011a099af5dc76498918ed7df445635b',
            'git_short_log': 'bbf5c979011a ("Linux 5.9")',
            'kernel_version': '5.9.0',
            'kconfig': ['tinyconfig'],
            'target_arch': 'x86_64',
            'toolchain': 'gcc-10',
            'download_url': build_download_url,
            'config': f'{build_download_url}/config',
            'does_not_exist': None,
            'build_name': 'tux-build',
        }

        expected_tests = {
            'build/tux-build': 'pass',
        }

        expected_metrics = {
            'build/tux-build-duration': '42',
            'build/tux-build-warnings': '2',
        }

        with requests_mock.Mocker() as fake_request:
            fake_request.get(build_url, json=build_results)
            fake_request.get(urljoin(build_download_url, 'build.log'), text=build_logs)

            status, completed, metadata, tests, metrics, logs = self.tuxsuite.fetch(testjob)
            self.assertEqual('Complete', status)
            self.assertTrue(completed)
            self.assertEqual(sorted(expected_metadata.items()), sorted(metadata.items()))
            self.assertEqual(sorted(expected_tests.items()), sorted(tests.items()))
            self.assertEqual(sorted(expected_metrics.items()), sorted(metrics.items()))
            self.assertEqual(build_logs, logs)

        self.assertEqual(build_results['build_name'], testjob.name)

    def test_retry_fetching_build_results(self):
        job_id = 'BUILD:tuxgroup@tuxproject#124'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        build_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/builds/124')
        build_download_url = 'http://builds.tuxbuild.com/124'

        build_results = {
            'retry': 0,  # this is the number of retry attempts TuxSuite has tried building
            'state': 'finished',
            'build_status': 'error',
            'build_name': 'tux-build',
            'git_repo': 'https://github.com/Linaro/linux-canaries.git',
            'git_ref': 'v5.9',
            'git_describe': 'v5.9',
            'git_sha': 'bbf5c979011a099af5dc76498918ed7df445635b',
            'git_short_log': 'bbf5c979011a ("Linux 5.9")',
            'kernel_version': '5.9.0',
            'kconfig': ['tinyconfig'],
            'target_arch': 'x86_64',
            'toolchain': 'gcc-10',
            'download_url': build_download_url,
            'provisioning_time': '2022-03-25T15:42:06.570362',
            'running_time': '2022-03-25T15:44:16.223590',
            'finished_time': '2022-03-25T15:46:56.095902',
            'warnings_count': '2',
            'status_message': 'Infrastructure Error, Please retry',
        }

        with requests_mock.Mocker() as fake_request:
            fake_request.get(build_url, json=build_results)

            with self.assertRaises(TemporaryFetchIssue):
                self.tuxsuite.fetch(testjob)

        self.assertEqual(build_results['build_name'], testjob.name)

    def test_fetch_build_with_given_up_infra_error(self):
        "this will test that the backend will still fetch the build despite its errored state"
        job_id = 'BUILD:tuxgroup@tuxproject#125'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        build_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/builds/125')
        build_download_url = 'http://builds.tuxbuild.com/125'

        build_logs = ''
        build_results = {
            'retry': 2,
            'state': 'finished',
            'build_status': 'error',
            'build_name': 'tux-build',
            'git_repo': 'https://github.com/Linaro/linux-canaries.git',
            'git_ref': 'v5.9',
            'git_describe': 'v5.9',
            'git_sha': 'bbf5c979011a099af5dc76498918ed7df445635b',
            'git_short_log': 'bbf5c979011a ("Linux 5.9")',
            'kernel_version': '5.9.0',
            'kconfig': ['tinyconfig'],
            'target_arch': 'x86_64',
            'toolchain': 'gcc-10',
            'download_url': build_download_url,
            'provisioning_time': '2022-03-25T15:42:06.570362',
            'running_time': '2022-03-25T15:44:16.223590',
            'finished_time': '2022-03-25T15:46:56.095902',
            'warnings_count': '2',
        }

        expected_metadata = {
            'job_url': build_url,
            'build_status': 'error',
            'git_repo': 'https://github.com/Linaro/linux-canaries.git',
            'git_ref': 'v5.9',
            'git_describe': 'v5.9',
            'git_sha': 'bbf5c979011a099af5dc76498918ed7df445635b',
            'git_short_log': 'bbf5c979011a ("Linux 5.9")',
            'kernel_version': '5.9.0',
            'kconfig': ['tinyconfig'],
            'target_arch': 'x86_64',
            'toolchain': 'gcc-10',
            'download_url': build_download_url,
            'config': f'{build_download_url}/config',
            'does_not_exist': None,
            'build_name': 'tux-build',
        }

        expected_tests = {
            'build/tux-build': 'skip',
        }

        expected_metrics = {}

        with requests_mock.Mocker() as fake_request:
            fake_request.get(build_url, json=build_results)
            fake_request.get(urljoin(build_download_url, 'build.log'), status_code=404)

            status, completed, metadata, tests, metrics, logs = self.tuxsuite.fetch(testjob)
            self.assertEqual('Incomplete', status)
            self.assertTrue(completed)
            self.assertEqual(sorted(expected_metadata.items()), sorted(metadata.items()))
            self.assertEqual(sorted(expected_tests.items()), sorted(tests.items()))
            self.assertEqual(sorted(expected_metrics.items()), sorted(metrics.items()))
            self.assertEqual(build_logs, logs)

        self.assertEqual(build_results['build_name'], testjob.name)

    def test_fetch_test_results(self):
        job_id = 'TEST:tuxgroup@tuxproject#123'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        test_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/tests/123')
        build_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/builds/456')

        # Only fetch when finished
        with requests_mock.Mocker() as fake_request:
            fake_request.get(test_url, json={'state': 'running'})
            results = self.tuxsuite.fetch(testjob)
            self.assertEqual(None, results)

        test_logs = 'dummy test log'
        test_results = {
            'project': 'tuxgroup/tuxproject',
            'device': 'qemu-armv7',
            'uid': '123',
            'kernel': 'https://storage.tuxboot.com/armv7/zImage',
            'ap_romfw': None,
            'mcp_fw': None,
            'mcp_romfw': None,
            'modules': None,
            'parameters': {},
            'rootfs': None,
            'scp_fw': None,
            'scp_romfw': None,
            'fip': None,
            'tests': ['boot', 'ltp-smoke'],
            'user': 'tuxbuild@linaro.org',
            'user_agent': 'tuxsuite/0.43.6',
            'state': 'finished',
            'result': 'pass',
            'results': {'boot': 'pass', 'ltp-smoke': 'pass'},
            'plan': None,
            'waiting_for': '456',
            'boot_args': None,
            'provisioning_time': '2022-03-25T15:49:11.441860',
            'running_time': '2022-03-25T15:50:11.770607',
            'finished_time': '2022-03-25T15:52:42.672483',
            'retries': 0,
            'retries_messages': [],
            'duration': 151
        }
        build_results = {
            'toolchain': 'gcc-10',
            'kconfig': ['defconfig', 'CONFIG_DUMMY=1'],
        }

        build_name = self.tuxsuite.generate_test_name(build_results)
        expected_metadata = {
            'job_url': test_url,
            'build_name': build_name,
            'does_not_exist': None,
            'toolchain': 'gcc-10',
            'kconfig': ['defconfig', 'CONFIG_DUMMY=1'],
        }

        # Real test results are stored in test/ci/backend/tuxsuite_test_result_sample.json
        with open('test/ci/backend/tuxsuite_test_result_sample.json') as test_result_file:
            test_results_json = json.load(test_result_file)

        expected_tests = {
            f'boot/{build_name}': 'pass',
            'ltp-smoke/access01': 'pass',
            'ltp-smoke/chdir01': 'skip',
            'ltp-smoke/fork01': 'pass',
            'ltp-smoke/time01': 'pass',
            'ltp-smoke/wait02': 'pass',
            'ltp-smoke/write01': 'pass',
            'ltp-smoke/symlink01': 'pass',
            'ltp-smoke/stat04': 'pass',
            'ltp-smoke/utime01A': 'pass',
            'ltp-smoke/rename01A': 'pass',
            'ltp-smoke/splice02': 'pass',
            'ltp-smoke/shell_test01': 'pass',
            'ltp-smoke/ping01': 'skip',
            'ltp-smoke/ping602': 'skip'
        }

        expected_metrics = {}

        with requests_mock.Mocker() as fake_request:
            fake_request.get(test_url, json=test_results)
            fake_request.get(build_url, json=build_results)
            fake_request.get(urljoin(test_url + '/', 'logs'), text=test_logs)
            fake_request.get(urljoin(test_url + '/', 'results'), json=test_results_json)

            status, completed, metadata, tests, metrics, logs = self.tuxsuite.fetch(testjob)
            self.assertEqual('Complete', status)
            self.assertTrue(completed)
            self.assertEqual(sorted(expected_metadata.items()), sorted(metadata.items()))
            self.assertEqual(sorted(expected_tests.items()), sorted(tests.items()))
            self.assertEqual(sorted(expected_metrics.items()), sorted(metrics.items()))
            self.assertEqual(test_logs, logs)

        self.assertEqual('ltp-smoke', testjob.name)

    def test_fetch_test_failed_results(self):
        job_id = 'TEST:tuxgroup@tuxproject#125'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        test_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/tests/125')
        build_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/builds/567')

        # Only fetch when finished
        with requests_mock.Mocker() as fake_request:
            fake_request.get(test_url, json={'state': 'running'})
            results = self.tuxsuite.fetch(testjob)
            self.assertEqual(None, results)

        test_logs = 'dummy test log'
        test_results = {
            'project': 'tuxgroup/tuxproject',
            'device': 'qemu-armv7',
            'uid': '125',
            'kernel': 'https://storage.tuxboot.com/armv7/zImage',
            'ap_romfw': None,
            'mcp_fw': None,
            'mcp_romfw': None,
            'modules': None,
            'parameters': {},
            'rootfs': None,
            'scp_fw': None,
            'scp_romfw': None,
            'fip': None,
            'tests': ['boot', 'ltp-smoke'],
            'user': 'tuxbuild@linaro.org',
            'user_agent': 'tuxsuite/0.43.6',
            'state': 'finished',
            'result': 'fail',
            'results': {'boot': 'fail', 'ltp-smoke': 'unknown'},
            'plan': None,
            'waiting_for': '567',
            'boot_args': None,
            'provisioning_time': '2022-03-25T15:49:11.441860',
            'running_time': '2022-03-25T15:50:11.770607',
            'finished_time': '2022-03-25T15:52:42.672483',
            'retries': 0,
            'retries_messages': [],
            'duration': 151
        }
        build_results = {
            'toolchain': 'gcc-10',
            'kconfig': ['defconfig', 'CONFIG_DUMMY=1'],
        }

        build_name = self.tuxsuite.generate_test_name(build_results)

        expected_metadata = {
            'job_url': test_url,
            'build_name': build_name,
            'does_not_exist': None,
            'toolchain': 'gcc-10',
            'kconfig': ['defconfig', 'CONFIG_DUMMY=1'],
        }

        # Real test results are stored in test/ci/backend/tuxsuite_test_failed_result_sample.json
        with open('test/ci/backend/tuxsuite_test_failed_result_sample.json') as test_result_file:
            test_results_json = json.load(test_result_file)

        expected_tests = {
            f'boot/{build_name}': 'fail',
            'ltp-smoke/access01': 'fail',
            'ltp-smoke/chdir01': 'skip',
            'ltp-smoke/fork01': 'pass',
            'ltp-smoke/time01': 'pass',
            'ltp-smoke/wait02': 'pass',
            'ltp-smoke/write01': 'pass',
            'ltp-smoke/symlink01': 'pass',
            'ltp-smoke/stat04': 'pass',
            'ltp-smoke/utime01A': 'pass',
            'ltp-smoke/rename01A': 'pass',
            'ltp-smoke/splice02': 'pass',
            'ltp-smoke/shell_test01': 'pass',
            'ltp-smoke/ping01': 'skip',
            'ltp-smoke/ping602': 'skip'
        }

        expected_metrics = {}

        with requests_mock.Mocker() as fake_request:
            fake_request.get(test_url, json=test_results)
            fake_request.get(build_url, json=build_results)
            fake_request.get(urljoin(test_url + '/', 'logs'), text=test_logs)
            fake_request.get(urljoin(test_url + '/', 'results'), json=test_results_json)

            status, completed, metadata, tests, metrics, logs = self.tuxsuite.fetch(testjob)
            self.assertEqual('Complete', status)
            self.assertTrue(completed)
            self.assertEqual(sorted(expected_metadata.items()), sorted(metadata.items()))
            self.assertEqual(sorted(expected_tests.items()), sorted(tests.items()))
            self.assertEqual(sorted(expected_metrics.items()), sorted(metrics.items()))
            self.assertEqual(test_logs, logs)

        self.assertEqual('ltp-smoke', testjob.name)
        self.assertEqual("{'boot': 'fail', 'ltp-smoke': 'unknown'}", testjob.failure)

    def test_fetch_test_results_for_test_with_failed_build(self):
        job_id = 'TEST:tuxgroup@tuxproject#124'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        test_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/tests/124')

        # Only fetch when finished
        with requests_mock.Mocker() as fake_request:
            fake_request.get(test_url, json={'state': 'running'})
            results = self.tuxsuite.fetch(testjob)
            self.assertEqual(None, results)

        test_logs = ''
        test_results = {
            'project': 'tuxgroup/tuxproject',
            'device': 'qemu-armv7',
            'uid': '124',
            'kernel': 'https://storage.tuxboot.com/armv7/zImage',
            'ap_romfw': None,
            'mcp_fw': None,
            'mcp_romfw': None,
            'modules': None,
            'parameters': {},
            'rootfs': None,
            'scp_fw': None,
            'scp_romfw': None,
            'fip': None,
            'tests': ['boot', 'ltp-smoke'],
            'user': 'tuxbuild@linaro.org',
            'user_agent': 'tuxsuite/0.43.6',
            'state': 'finished',
            'result': 'fail',
            'results': {},
            'plan': None,
            'waiting_for': None,
            'boot_args': None,
            'provisioning_time': '2022-03-25T15:49:11.441860',
            'running_time': '2022-03-25T15:50:11.770607',
            'finished_time': '2022-03-25T15:52:42.672483',
            'retries': 0,
            'retries_messages': [],
            'duration': 151
        }

        expected_metadata = {
            'job_url': test_url,
            'does_not_exist': None,
        }

        expected_tests = {}

        expected_metrics = {}

        with requests_mock.Mocker() as fake_request:
            fake_request.get(test_url, json=test_results)
            fake_request.get(urljoin(test_url + '/', 'logs'), text='{"error": "File not found"}', status_code=404)
            fake_request.get(urljoin(test_url + '/', 'results'), json={'error': 'File not found'}, status_code=404)

            status, completed, metadata, tests, metrics, logs = self.tuxsuite.fetch(testjob)
            self.assertEqual('Complete', status)
            self.assertTrue(completed)
            self.assertEqual(sorted(expected_metadata.items()), sorted(metadata.items()))
            self.assertEqual(sorted(expected_tests.items()), sorted(tests.items()))
            self.assertEqual(sorted(expected_metrics.items()), sorted(metrics.items()))
            self.assertEqual(test_logs, logs)

        self.assertEqual('ltp-smoke', testjob.name)
        self.assertEqual('build failed', testjob.failure)

    def test_fetch_test_results_unknown(self):
        job_id = 'TEST:tuxgroup@tuxproject#125'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        test_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/tests/125')

        test_results = {
            'project': 'tuxgroup/tuxproject',
            'device': 'qemu-armv7',
            'uid': '124',
            'kernel': 'https://storage.tuxboot.com/armv7/zImage',
            'ap_romfw': None,
            'mcp_fw': None,
            'mcp_romfw': None,
            'modules': None,
            'parameters': {},
            'rootfs': None,
            'scp_fw': None,
            'scp_romfw': None,
            'fip': None,
            'tests': ['boot', 'ltp-smoke'],
            'user': 'tuxbuild@linaro.org',
            'user_agent': 'tuxsuite/0.43.6',
            'state': 'finished',
            'result': 'fail',
            'results': {'boot': 'unknown', 'ltp-mm': 'unknown'},
            'plan': None,
            'waiting_for': None,
            'boot_args': None,
            'provisioning_time': '2022-03-25T15:49:11.441860',
            'running_time': '2022-03-25T15:50:11.770607',
            'finished_time': '2022-03-25T15:52:42.672483',
            'retries': 0,
            'retries_messages': [],
            'duration': 151
        }

        with requests_mock.Mocker() as fake_request:
            fake_request.get(test_url, json=test_results)

            self.assertEqual(None, self.tuxsuite.fetch(testjob))
