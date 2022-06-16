from django.test import TestCase
import requests_mock


from squad.core.models import Group, Status
from squad.ci.models import Backend

from squad.core.plugins import get_plugin_instance

"""
    This tests SQUAD's compatibility with the Tradefed plugin that might
    be enabled in projects.

    In order to be closer to a real execution of tradefed, there's a sample
    of a tradefed tar ball adjusted from one of the jobs in LAVA. The only difference
    is in size. The actual file is over 100MB, and since we're keeping it
    in the repository, it wouldn't be convenient to store that. The file
    was striped in a file of 0.5MB.

    The most important file is `test_results.xml`, which contains a list of all
    passing an failing tests, along with logs. The one located in the tar ball has
    the following pattern:

    <?xml version='1.0' encoding='UTF-8' standalone='no' ?>
    <?xml-stylesheet type="text/xsl" href="compatibility_result.xsl"?>
    <Result ...>
        <Build ...>
            <Summary pass="972406" failed="5" modules_done="1" modules_total="1" />
            <Module name="CtsDeqpTestCases" abi="arm64-v8a" runtime="4310214" done="true" pass="972406" total_tests="972411">
                <TestCase name="dEQP-EGL.info">
                    <Test result="pass" name="version" />
                    <Test result="pass" name="vendor" />
                    <Test result="pass" name="client_apis" />
                    <Test result="pass" name="extensions" />
                    <Test result="pass" name="configs" />
                </TestCase>
            </Module>
        </Build>
    </Result>

    There are
    * 1 Module tag
    * 285 TestCase tags
    * 6273 Test tags
      * 6272 passes
      * 1 fail
"""


definition = """
actions:
- test:
    docker:
      image: yongqinliu/linaro-android-docker:0.1
    timeout:
      minutes: 5
    definitions:
    - from: inline
      path: format-metatdata.yaml
      name: format-metatdata
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: format-metatdata
          description: format-metatdata
        run:
          steps:
          - lava-test-case "format-metadata" --shell fastboot format:ext4 metadata
- test:
    docker:
      image: yongqinliu/linaro-android-docker:0.1
    timeout:
      minutes: 900
    definitions:
    - repository: https://github.com/Linaro/test-definitions.git
      from: git
      path: automated/android/noninteractive-tradefed/tradefed.yaml
      params:
        TEST_PARAMS: cts-presubmit --abi arm64-v8a -m CtsDeqpTestCases --disable-reboot
        TEST_URL: http://testdata.linaro.org/lkft/aosp-stable/android/lkft/lkft-aosp-android12-cts/332/android-cts.zip
        TEST_PATH: android-cts
        RESULTS_FORMAT: aggregated
        ANDROID_VERSION: aosp-android12
      name: cts-lkft
"""

job_suites = {
    'count': 1,
    'next': None,
    'previous': None,
    'results': [
        {
            'id': 1,
            'resource_uri': 'http://lava.server/api/v0.2/jobs/5149627/suites/12261981/',
            'name': '3_cts-lkft',
            'job': 5149627
        },
    ],
}

suite_attachments = {
    'count': 1,
    'next': None,
    'previous': None,
    'results': [
        {
            'id': 789133853,
            'result': 'pass',
            'resource_uri': 'http://lava.server/api/v0.2/jobs/5149627/suites/12261981/tests/789133853/',
            'unit': '',
            'name': 'test-attachment',
            'measurement': None,
            'metadata': "{case: test-attachment, definition: 3_cts-lkft, reference: 'http://attachment.server/artifacts/team/qa/2022/06/08/10/55/tradefed-output-20220608105250.tar.xz',\n  result: pass}\n",
            'start_log_line': None,
            'end_log_line': None,
            'logged': '2022-06-08T10:55:14.655858Z',
            'suite': 12261981,
            'test_set': None
        }
    ]
}

with open('test/integration/plugins/tradefed-output-20220608105250.tar.xz', 'rb') as f:
    tar_contents = f.read()


class TestTradefed(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug="mygroup")
        self.project = self.group.projects.create(slug="myproject", project_settings="PLUGINS_TRADEFED_EXTRACT_AGGREGATED: True")
        self.build = self.project.builds.create(version="tradefed-build")
        self.env = self.project.environments.create(slug="myenv")
        self.testrun = self.build.test_runs.create(environment=self.env)
        self.backend = Backend.objects.create(url="http://lava.server/api/v0.2/", name="tradefed-backend", implementation_type="lava")
        self.testjob = self.build.test_jobs.create(definition=definition, target=self.project, backend=self.backend, job_id="123", testrun=self.testrun)
        self.tradefed = get_plugin_instance('tradefed')

    def test_parse_cts_results(self):

        with requests_mock.Mocker() as m:
            m.get('http://lava.server/api/v0.2/jobs/123/suites/', json=job_suites)
            m.get('http://lava.server/api/v0.2/jobs/123/suites/1/tests/', json=suite_attachments)
            m.get('http://attachment.server/artifacts/team/qa/2022/06/08/10/55/tradefed-output-20220608105250.tar.xz', content=tar_contents)
            self.tradefed.postprocess_testjob(self.testjob)

        self.testrun.refresh_from_db()

        # Check that the status has been recorded
        self.assertTrue(self.testrun.status_recorded)
        status = Status.objects.get(test_run=self.testrun, suite=None)
        self.assertEqual(6272, status.tests_pass)
        self.assertEqual(1, status.tests_fail)

        # Check that the failed test contain the proper log
        failed_test = self.testrun.tests.filter(result=False).first()
        expected_log = 'with config {glformat=rgba8888d24s8ms0,rotation=unspecified,surfacetype=window,required=true}'
        self.assertIn(expected_log, failed_test.log)

        # Check that the attachment was saved to the testrun
        self.assertTrue(self.testrun.attachments.count() > 0)
