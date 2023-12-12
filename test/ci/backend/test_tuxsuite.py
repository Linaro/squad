import base64
import hashlib
import requests
import requests_mock
import json

from urllib.parse import urljoin
from django.test import TestCase
from unittest.mock import MagicMock, Mock, patch
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization

from squad.ci.backend.tuxsuite import Backend as TuxSuiteBackend
from squad.ci.exceptions import FetchIssue, TemporaryFetchIssue
from squad.ci.models import Backend, TestJob
from squad.core.models import Group, Project
from squad.core.tasks import ReceiveTestRun


TUXSUITE_URL = 'http://testing.tuxsuite.com'

# ssh-keygen -t ecdsa -b 256 -m PEM
PRIVATE_SSH_KEY = """-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIDSs6JYNlBeOFfifuEt08LhaSpYWj1GgylYo3zZHPamJoAoGCCqGSM49
AwEHoUQDQgAE77r6UW93IGYjGfPU9OWPqucHpXZrRU5PcH+pZrOElj0h+nkA6hMW
VPGqPoiohMdneJVO/rXWuwQLxUNgKAeHJQ==
-----END EC PRIVATE KEY-----"""

PUBLIC_SSH_KEY = "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBO+6+lFvdyBmIxnz1PTlj6rnB6V2a0VOT3B/qWazhJY9Ifp5AOoTFlTxqj6IqITHZ3iVTv611rsEC8VDYCgHhyU="


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
                    "OEBUILD_METADATA_KEYS": [
                        "download_url",
                        "sources",
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
        self.environment = self.project.environments.create(slug="myenv")
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

        result = self.tuxsuite.parse_job_id('TEST:linaro.ltd@anders.roxel#1yPYGaOEPNwr2pCqBgONY43zORq')
        self.assertEqual(('TEST', 'linaro.ltd@anders.roxel', '1yPYGaOEPNwr2pCqBgONY43zORq'), result)

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

    def test_parse_test_no_metadata(self):
        results = {
            'download_url': 'http://builds.tuxbuild.com/123',
        }

        metadata = dict()
        expected = dict()
        with requests_mock.Mocker() as fake_request:
            fake_request.get(results['download_url'] + '/' + 'metadata.json', status_code=404)
            self.tuxsuite.update_metadata_from_file(results=results, metadata=metadata)

        self.assertEqual(expected, metadata)

    def test_parse_test_metadata(self):
        results = {
            'download_url': 'http://builds.tuxbuild.com/123',
        }

        metadata = {
            "example_metadata": "blah",
        }

        metadata_file = {
            "arch": "arm64",
            "host_arch": "amd64",
            "qemu_version": "1:8.1.2+ds-1",
            "artefacts": {
                "rootfs": {
                    "url": "https://storage.tuxboot.com/debian/bookworm/arm64/rootfs.ext4.xz",
                    "sha256sum": "5e0a9ec562ffea3d9705834677df1cd43ff1ba44228b46734e10a5e990c2c169",
                },
                "kernel": {
                    "url": "https://storage.tuxsuite.com/public/linaro/lkft/builds/2ZPQut79EaVwA8ANRJp7xaAVkpP/Image.gz",
                    "sha256sum": "ab5d2ef97d7a7da95032899c3ee9233dcdf75a4091ec03d7ae2d53f05d24e114",
                },
                "modules": {
                    "url": "https://storage.tuxsuite.com/public/linaro/lkft/builds/2ZPQut79EaVwA8ANRJp7xaAVkpP/modules.tar.xz",
                    "sha256sum": "1602a287bb54f43e9d4e589c9a773cbd7b9d1bee336501792092a25d76d0f3fc",
                },
                "overlay-00": {
                    "url": "https://storage.tuxboot.com/overlays/debian/bookworm/arm64/ltp/20230929/ltp.tar.xz",
                    "sha256sum": "94ff90b59487ceb765b09a53d6642ce0e39deaa92062687355a99de3652130e0",
                },
            },
            "durations": {"tests": {"ltp-controllers": "4250.66", "boot": "62.69"}},
        }

        expected = {
            "example_metadata": "blah",
            "arch": "arm64",
            "host_arch": "amd64",
            "qemu_version": "1:8.1.2+ds-1",
            "artefacts": {
                "rootfs": {
                    "url": "https://storage.tuxboot.com/debian/bookworm/arm64/rootfs.ext4.xz",
                    "sha256sum": "5e0a9ec562ffea3d9705834677df1cd43ff1ba44228b46734e10a5e990c2c169",
                },
                "kernel": {
                    "url": "https://storage.tuxsuite.com/public/linaro/lkft/builds/2ZPQut79EaVwA8ANRJp7xaAVkpP/Image.gz",
                    "sha256sum": "ab5d2ef97d7a7da95032899c3ee9233dcdf75a4091ec03d7ae2d53f05d24e114",
                },
                "modules": {
                    "url": "https://storage.tuxsuite.com/public/linaro/lkft/builds/2ZPQut79EaVwA8ANRJp7xaAVkpP/modules.tar.xz",
                    "sha256sum": "1602a287bb54f43e9d4e589c9a773cbd7b9d1bee336501792092a25d76d0f3fc",
                },
                "overlay-00": {
                    "url": "https://storage.tuxboot.com/overlays/debian/bookworm/arm64/ltp/20230929/ltp.tar.xz",
                    "sha256sum": "94ff90b59487ceb765b09a53d6642ce0e39deaa92062687355a99de3652130e0",
                },
            },
            "durations": {"tests": {"ltp-controllers": "4250.66", "boot": "62.69"}},
        }

        with requests_mock.Mocker() as fake_request:
            fake_request.get(results["download_url"] + '/' + 'metadata.json', json=metadata_file)
            self.tuxsuite.update_metadata_from_file(results=results, metadata=metadata)

        self.assertEqual(expected, metadata)

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

    @patch("squad.ci.backend.tuxsuite.Backend.fetch_from_results_input")
    def test_fetch_build_results(self, mock_fetch_from_results_input):
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
            'job_id': job_id,
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
        mock_fetch_from_results_input.assert_not_called()

    @patch("squad.ci.backend.tuxsuite.Backend.fetch_from_results_input")
    def test_retry_fetching_build_results(self, mock_fetch_from_results_input):
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
        mock_fetch_from_results_input.assert_not_called()

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
            'job_id': job_id,
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
            'job_id': job_id,
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

    def test_fetch_test_results_no_build_name_for_oebuilds(self):
        job_id = 'TEST:tuxgroup@tuxproject#1234'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        test_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/tests/1234')

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
            'waiting_for': 'OEBUILD#2Wetiz7Qs0TbtfPgPT7hUObWqDK',
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
            'job_id': job_id,
            'does_not_exist': None,
        }

        # Real test results are stored in test/ci/backend/tuxsuite_test_result_sample.json
        with open('test/ci/backend/tuxsuite_test_result_sample.json') as test_result_file:
            test_results_json = json.load(test_result_file)

        expected_tests = {
            'boot/boot': 'pass',
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

    def test_fetch_results_from_testjob_input(self):
        job_id = 'TEST:tuxgroup@tuxproject#123'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        test_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/tests/123')
        build_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/builds/456')

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
            'job_id': job_id,
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

        job_data = {
            'download_url': 'http://storage.tuxapi.com/mystorage'
        }

        expected_metrics = {}

        testjob.input = json.dumps(test_results)
        with requests_mock.Mocker() as fake_request:
            fake_request.get(build_url, json=build_results)
            fake_request.get(urljoin(test_url + '/', 'logs'), text=test_logs)
            fake_request.get(urljoin(test_url + '/', 'results'), json=test_results_json)
            fake_request.get(test_url, json=job_data)

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
            'job_id': job_id,
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

    def test_fetch_test_infrastructure_error(self):
        job_id = 'TEST:tuxgroup@tuxproject#126'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        test_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/tests/126')

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
            'result': 'error',  # error means tuxsuite suffered from an infrastructure error and was not able to run tests
            'results': {'boot': 'unknown', 'ltp-smoke': 'unknown'},
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

        expected_metadata = {
            'job_url': test_url,
            'job_id': job_id,
            'does_not_exist': None,
        }

        with requests_mock.Mocker() as fake_request:
            fake_request.get(test_url, json=test_results)

            status, completed, metadata, tests, metrics, logs = self.tuxsuite.fetch(testjob)
            self.assertEqual('Incomplete', status)
            self.assertTrue(completed)
            self.assertEqual(sorted(expected_metadata.items()), sorted(metadata.items()))
            self.assertEqual({}, tests)
            self.assertEqual({}, metrics)
            self.assertEqual('', logs)

        self.assertEqual('ltp-smoke', testjob.name)
        self.assertEqual('tuxsuite infrastructure error', testjob.failure)

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
            'job_id': job_id,
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

    def test_follow_test_dependency(self):
        job_id = 'TEST:tuxgroup@tuxproject#124'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        test_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/tests/124')
        sanity_test_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/tests/123')
        build_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/builds/456')

        test_logs = 'dummy test log'
        test_results = {
            'project': 'tuxgroup/tuxproject',
            'uid': '124',
            'tests': ['boot', 'ltp-smoke'],
            'state': 'finished',
            'result': 'pass',
            'results': {'boot': 'pass', 'ltp-smoke': 'pass'},
            'plan': None,
            'waiting_for': 'TEST#123',
        }
        sanity_test_results = {
            'project': 'tuxgroup/tuxproject',
            'uid': '123',
            'waiting_for': 'BUILD#456',
        }
        build_results = {
            'toolchain': 'gcc-10',
            'kconfig': ['defconfig', 'CONFIG_DUMMY=1'],
        }

        build_name = self.tuxsuite.generate_test_name(build_results)
        expected_metadata = {
            'job_url': test_url,
            'job_id': job_id,
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
            fake_request.get(sanity_test_url, json=sanity_test_results)
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

            self.assertEqual(5, fake_request.call_count)

        self.assertEqual('ltp-smoke', testjob.name)

    def test_follow_test_dependency_using_cached_testrun(self):
        job_id = 'TEST:tuxgroup@tuxproject#124'
        sanity_job_id = 'TEST:tuxgroup@tuxproject#112233'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        sanity_testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=sanity_job_id)
        test_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/tests/124')
        sanity_test_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/tests/112233')
        build_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/builds/456')

        test_logs = 'dummy test log'
        test_results = {
            'project': 'tuxgroup/tuxproject',
            'uid': '124',
            'tests': ['boot', 'ltp-smoke'],
            'state': 'finished',
            'result': 'pass',
            'results': {'boot': 'pass', 'ltp-smoke': 'pass'},
            'plan': None,
            'waiting_for': 'TEST#112233',
        }
        sanity_test_results = {
            'project': 'tuxgroup/tuxproject',
            'uid': '112233',
            'waiting_for': 'BUILD#456',
            'project': 'tuxgroup/tuxproject',
            'tests': ['boot', 'ltp-smoke'],
            'state': 'finished',
            'result': 'pass',
            'results': {'boot': 'pass', 'ltp-smoke': 'pass'},
            'plan': None,
        }
        build_results = {
            'toolchain': 'gcc-10',
            'kconfig': ['defconfig', 'CONFIG_DUMMY=1'],
        }

        build_name = self.tuxsuite.generate_test_name(build_results)

        # Real test results are stored in test/ci/backend/tuxsuite_test_result_sample.json
        with open('test/ci/backend/tuxsuite_test_result_sample.json') as test_result_file:
            test_results_json = json.load(test_result_file)

        with requests_mock.Mocker() as fake_request:
            fake_request.get(test_url, json=test_results)
            fake_request.get(sanity_test_url, json=sanity_test_results)
            fake_request.get(build_url, json=build_results)
            fake_request.get(urljoin(test_url + '/', 'logs'), text=test_logs)
            fake_request.get(urljoin(sanity_test_url + '/', 'logs'), text=test_logs)
            fake_request.get(urljoin(test_url + '/', 'results'), json=test_results_json)
            fake_request.get(urljoin(sanity_test_url + '/', 'results'), json=test_results_json)

            # Fetch sanity job first
            status, completed, metadata, tests, metrics, logs = self.tuxsuite.fetch(sanity_testjob)
            receive = ReceiveTestRun(sanity_testjob.target, update_project_status=False)
            testrun, _ = receive(
                version=sanity_testjob.target_build.version,
                environment_slug=sanity_testjob.environment,
                metadata_file=json.dumps(metadata),
                tests_file=json.dumps(tests),
                metrics_file=json.dumps(metrics),
                log_file=logs,
                completed=completed,
            )
            self.assertEqual(4, fake_request.call_count)

            # Now fetch test, and make sure no extra requests were made
            _, _, metadata, _, _, _ = self.tuxsuite.fetch(testjob)
            self.assertEqual(build_name, metadata['build_name'])
            self.assertEqual(7, fake_request.call_count)

        self.assertEqual('ltp-smoke', testjob.name)

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

    def test_cancel(self):
        job_id = 'TEST:tuxgroup@tuxproject#125'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        with requests_mock.Mocker() as fake_request:
            url = f'{TUXSUITE_URL}/groups/tuxgroup/projects/tuxproject/tests/125/cancel'
            fake_request.post(url, status_code=200)
            self.assertTrue(self.tuxsuite.cancel(testjob))

        # Mock a failed cancellation
        job_id = 'TEST:tuxgroup@tuxproject#126'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        with requests_mock.Mocker() as fake_request:
            url = f'{TUXSUITE_URL}/groups/tuxgroup/projects/tuxproject/tests/126/cancel'
            fake_request.post(url, status_code=400)
            self.assertFalse(self.tuxsuite.cancel(testjob))

    def test_callback_is_supported(self):
        self.assertTrue(self.tuxsuite.supports_callbacks())

    def test_validate_callback(self):
        request = Mock()
        request.headers = {}
        request.json = MagicMock(return_value={})
        request.body = b'"{\\"content\\": 1}"'

        # Missing signature header
        with self.assertRaises(Exception) as ctx:
            self.tuxsuite.validate_callback(request, self.project)
            self.assertEqual("tuxsuite request is missing signature headers", str(ctx.exception))

        # Missing public key
        request.headers = {
            "x-tux-payload-signature": "does-not-work_6bUINPk62PaJb73C3bfKVvntgpr2Ii2TzQAiEA2D5-jKuh4xa4TkVhIA0UzvKERKKflpFjBH3hlsWivzI=",
        }
        with self.assertRaises(Exception) as ctx:
            self.tuxsuite.validate_callback(request, self.project)
            self.assertEqual("missing tuxsuite public key for this project", str(ctx.exception))

        # Invalid signature
        self.project.__settings__ = None
        self.project.project_settings = f"TUXSUITE_PUBLIC_KEY: \"{PUBLIC_SSH_KEY}\""
        with self.assertRaises(InvalidSignature) as ctx:
            self.tuxsuite.validate_callback(request, self.project)
            self.assertEqual("missing tuxsuite public key for this project", str(ctx.exception))

        # Generate signature with testing private key
        content = b'{"signed": "content"}'
        content_bytes = b'"{\\"signed\\": \\"content\\"}"'
        key = serialization.load_pem_private_key(PRIVATE_SSH_KEY.encode("ascii"), None)
        signature = key.sign(content, ec.ECDSA(hashes.SHA256()))
        valid_signature = base64.urlsafe_b64encode(signature)
        request.headers = {"x-tux-payload-signature": valid_signature}
        request.body = content_bytes
        self.tuxsuite.validate_callback(request, self.project)

    def test_process_callback(self):
        # Test missing kind/status key
        with self.assertRaises(Exception) as ctx:
            self.tuxsuite.process_callback({}, None, None, None)
            self.assertEqual("`kind` and `status` are required in the payload", str(ctx.exception))

        # Test creating new testjob
        payload = {
            "kind": "test",
            "status": {
                "project": "tuxgroup/tuxproject",
                "uid": "123",
                "device": self.environment.slug,
            },
        }

        self.assertFalse(TestJob.objects.filter(job_id="TEST:tuxgroup@tuxproject#123").exists())
        testjob = self.tuxsuite.process_callback(json.dumps(payload), self.build, self.environment.slug, self.backend)
        self.assertEqual(json.dumps(payload["status"]), testjob.input)
        self.assertTrue(TestJob.objects.filter(job_id="TEST:tuxgroup@tuxproject#123").exists())
        self.assertEqual(self.environment.slug, testjob.environment)

        # Test existing testjob
        payload["status"]["uid"] = "1234"
        testjob = TestJob.objects.create(
            backend=self.backend,
            target=self.project,
            target_build=self.build,
            environment=self.environment.slug,
            submitted=True,
            job_id="TEST:tuxgroup@tuxproject#1234",
        )
        self.assertEqual(None, testjob.input)
        returned_testjob = self.tuxsuite.process_callback(json.dumps(payload), self.build, self.environment.slug, self.backend)
        self.assertEqual(testjob.id, returned_testjob.id)
        self.assertEqual(json.dumps(payload["status"]), returned_testjob.input)

    @patch("squad.ci.backend.tuxsuite.Backend.fetch_from_results_input")
    def test_fetch_oe_build_results(self, mock_fetch_from_results_input):
        job_id = 'OEBUILD:tuxgroup@tuxproject#123'
        testjob = self.build.test_jobs.create(target=self.project, backend=self.backend, job_id=job_id)
        build_url = urljoin(TUXSUITE_URL, '/groups/tuxgroup/projects/tuxproject/oebuilds/123')
        build_download_url = 'http://builds.tuxbuild.com/123'

        # Only fetch when finished
        with requests_mock.Mocker() as fake_request:
            fake_request.get(build_url, json={'state': 'running'})
            results = self.tuxsuite.fetch(testjob)
            self.assertEqual(None, results)

        build_logs = 'dummy build log'
        build_results = {
            "artifacts": [],
            "bblayers_conf": [],
            "container": "ubuntu-20.04",
            "download_url": build_download_url,
            "environment": {},
            "errors_count": 0,
            "extraconfigs": [],
            "is_canceling": False,
            "is_public": True,
            "local_conf": [],
            "name": "",
            "no_cache": False,
            "plan": "2UyDaiGYNeHEYPD7hGjuuqmgZIn",
            "project": "linaro/lkft",
            "provisioning_time": "2023-09-05T08:36:32.853409",
            "result": "pass",
            "sources": {
                "android": {
                    "bazel": True,
                    "branch": "common-android-mainline",
                    "build_config": "//common:kernel_aarch64_dist",
                    "manifest": "default.xml",
                    "url": "https://android.googlesource.com/kernel/manifest"
                }
            },
            "state": "finished",
            "token_name": "lkft-android-bot",
            "uid": "2UyDaslU6koW0a85VVEh3Pc2LNW",
            "user": "lkft@linaro.org",
            "user_agent": "tuxsuite/1.25.1",
            "waited_by": [],
            "warnings_count": 0
        }

        expected_metadata = {
            'download_url': build_download_url,
            'sources': {
                'android': {
                    'bazel': True,
                    'branch': 'common-android-mainline',
                    'build_config': '//common:kernel_aarch64_dist',
                    'manifest': 'default.xml',
                    'url': 'https://android.googlesource.com/kernel/manifest'
                }
            },
            'job_url': build_url,
            'job_id': job_id,
        }

        expected_tests = {
            'build/build': 'pass',
        }

        expected_metrics = {}

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

        mock_fetch_from_results_input.assert_not_called()
