import json
import logging
import re
import requests
import ssl
import traceback
import yaml
import xmlrpc
import zmq

from zmq.utils.strtypes import u

from xmlrpc import client as xmlrpclib
from urllib.parse import urlsplit


from squad.ci.models import TestJob
from squad.ci.tasks import fetch, send_testjob_resubmit_admin_email
from squad.ci.exceptions import SubmissionIssue, TemporarySubmissionIssue
from squad.ci.exceptions import FetchIssue, TemporaryFetchIssue
from squad.ci.backend.null import Backend as BaseBackend


description = "LAVA"
logger = logging.getLogger('squad.ci.backend')


class Backend(BaseBackend):

    # ------------------------------------------------------------------------
    # API implementation
    # ------------------------------------------------------------------------
    def submit(self, test_job):
        try:
            job_id = self.__submit__(test_job.definition)
            test_job.name = self.__lava_job_name(test_job.definition)
            return job_id
        except xmlrpc.client.ProtocolError as error:
            raise TemporarySubmissionIssue(self.url_remove_token(str(error)))
        except xmlrpc.client.Fault as fault:
            if fault.faultCode // 100 == 5:
                # assume HTTP errors 5xx are temporary issues
                raise TemporarySubmissionIssue(self.url_remove_token(str(fault)))
            else:
                raise SubmissionIssue(self.url_remove_token(str(fault)))
        except ssl.SSLError as fault:
            raise SubmissionIssue(self.url_remove_token(str(fault)))

    def fetch(self, test_job):
        try:
            data = self.__get_job_details__(test_job.job_id)

            if data['status'] in self.complete_statuses:
                data['results'] = self.__get_testjob_results_yaml__(test_job.job_id)

                # fetch logs
                logs = ""
                try:
                    logs = self.__get_job_logs__(test_job.job_id)
                except Exception:
                    self.log_warn(("Logs for job %s are not available" % test_job.job_id) + "\n" + traceback.format_exc())

                return self.__parse_results__(data, test_job) + (logs,)
        except xmlrpc.client.ProtocolError as error:
            raise TemporaryFetchIssue(self.url_remove_token(str(error)))
        except xmlrpc.client.Fault as fault:
            if fault.faultCode // 100 == 5:
                # assume HTTP errors 5xx are temporary issues
                raise TemporaryFetchIssue(self.url_remove_token(str(fault)))
            else:
                raise FetchIssue(self.url_remove_token(str(fault)))
        except ssl.SSLError as fault:
            raise FetchIssue(self.url_remove_token(str(fault)))

    def listen(self):
        listener_url = self.get_listener_url()

        self.log_debug("connecting to %s" % listener_url)

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        try:
            # requires PyZMQ to be built against ZeroMQ 4.2+
            self.socket.setsockopt(zmq.HEARTBEAT_IVL, 1000)  # 1 s
            self.socket.setsockopt(zmq.HEARTBEAT_TIMEOUT, 10000)  # 10 s
        except AttributeError:
            self.log_warn('PyZMQ has no support for heartbeat (requires ZeroMQ library 4.2+), connection may be unstable')
            pass

        self.socket.connect(listener_url)

        self.log_debug("connected to %s" % listener_url)

        while True:
            try:
                message = self.socket.recv_multipart()
                (topic, uuid, dt, username, data) = (u(m) for m in message[:])
                data = json.loads(data)
                self.receive_event(topic, data)
            except Exception as e:
                self.log_error(str(e) + "\n" + traceback.format_exc())

    def job_url(self, test_job):
        url = urlsplit(self.data.url)
        joburl = '%s://%s/scheduler/job/%s' % (
            url.scheme,
            url.netloc,
            test_job.job_id
        )
        return joburl

    # ------------------------------------------------------------------------
    # implementation details
    # ------------------------------------------------------------------------
    def __init__(self, data):
        super(Backend, self).__init__(data)
        self.complete_statuses = ['Complete', 'Incomplete', 'Canceled']
        self.__proxy__ = None

    def url_remove_token(self, text):
        if self.data is not None and self.data.token is not None:
            return text.replace(self.data.token, "*****")
        return text

    @property
    def proxy(self):
        if self.__proxy__ is None:
            url = urlsplit(self.data.url)
            endpoint = '%s://%s:%s@%s%s' % (
                url.scheme,
                self.data.username,
                self.data.token,
                url.netloc,
                url.path
            )
            self.__proxy__ = xmlrpclib.ServerProxy(endpoint)
        return self.__proxy__

    def get_listener_url(self):
        url = urlsplit(self.data.url)
        hostname = url.netloc

        socket = self.__get_publisher_event_socket__()
        socket_url = urlsplit(socket)
        port = socket_url.port
        if socket_url.hostname != '*':
            hostname = socket_url.hostname
        scheme = socket_url.scheme
        return '%s://%s:%s' % (scheme, hostname, port)

    def resubmit(self, test_job):
        if test_job.job_id is not None:
            new_job_id = self.__resubmit__(test_job.job_id)
            new_test_job_name = None
            if test_job.definition is not None:
                new_test_job_name = self.__lava_job_name(test_job.definition)
            new_test_job = TestJob(
                backend=self.data,
                definition=test_job.definition,
                target=test_job.target,
                target_build=test_job.target_build,
                environment=test_job.environment,
                submitted=True,
                job_id=new_job_id,
                resubmitted_count=test_job.resubmitted_count + 1,
                name=new_test_job_name,
                parent_job=test_job,
            )
            test_job.can_resubmit = False
            test_job.save()
            new_test_job.save()
            return new_test_job
        return None

    def __lava_job_name(self, definition):
        yaml_definition = yaml.safe_load(definition)
        if 'job_name' in yaml_definition.keys():
            # only return first 255 characters
            return yaml_definition['job_name'][:255]
        return None

    def __resubmit__(self, job_id):
        return self.proxy.scheduler.resubmit_job(job_id)

    def __submit__(self, definition):
        return self.proxy.scheduler.submit_job(definition)

    def __get_job_details__(self, job_id):
        return self.proxy.scheduler.job_details(job_id)

    def __download_full_log__(self, job_id):
        url = self.data.url.replace('/RPC2', '/scheduler/job/%s/log_file/plain' % job_id)
        payload = {"user": self.data.username, "token": self.data.token}
        response = requests.get(url, params=payload)
        return response.content

    def __get_job_logs__(self, job_id):
        logger.debug("Retrieving logs job: %s" % job_id)
        log_data = self.__download_full_log__(job_id)
        return self.__parse_log__(log_data)

    def __parse_log__(self, log_data):
        returned_log = ""
        start_dict = False
        tmp_dict = None
        tmp_key = None
        is_value = False
        for event in yaml.parse(log_data, Loader=yaml.CLoader):
            if isinstance(event, yaml.MappingStartEvent):
                start_dict = True
                tmp_dict = {}
            if isinstance(event, yaml.MappingEndEvent):
                start_dict = False
                if tmp_dict:
                    if 'lvl' in tmp_dict.keys() and tmp_dict['lvl'] == 'target':
                        if 'msg' in tmp_dict.keys():
                            if isinstance(tmp_dict['msg'], bytes):
                                try:
                                    # seems like latin-1 is the encoding used by serial
                                    # this might not be true in all cases
                                    returned_log = returned_log + "\n" + tmp_dict["msg"].decode('latin-1', 'ignore')
                                except ValueError:
                                    # despite ignoring errors, they are still raised sometimes
                                    pass
                            else:
                                returned_log = returned_log + "\n" + tmp_dict['msg']
                del tmp_dict
                tmp_dict = None
                is_value = False
            if start_dict is True and isinstance(event, yaml.ScalarEvent):
                if is_value is False:
                    # the event.value is a dict key
                    tmp_key = event.value
                    is_value = True
                else:
                    # the event.value is a dict value
                    tmp_dict.update({tmp_key: event.value})
                    is_value = False

        return returned_log

    def __get_testjob_results_yaml__(self, job_id):
        logger.debug("Retrieving result summary for job: %s" % job_id)
        suites = self.proxy.results.get_testjob_suites_list_yaml(job_id)
        y = yaml.safe_load(suites)
        lava_job_results = []
        for suite in y:
            limit = 500
            offset = 0
            while True:
                logger.debug(
                    "requesting results for %s with offset of %s"
                    % (suite['name'], offset)
                )
                results = self.proxy.results.get_testsuite_results_yaml(
                    job_id,
                    suite['name'],
                    limit,
                    offset)
                yaml_results = yaml.load(results, Loader=yaml.CLoader)
                lava_job_results = lava_job_results + yaml_results
                if len(yaml_results) == limit:
                    offset = offset + limit
                else:
                    break

        return lava_job_results

    def __get_publisher_event_socket__(self):
        return self.proxy.scheduler.get_publisher_event_socket()

    def __parse_results__(self, data, test_job):
        handle_lava_suite = self.settings.get('CI_LAVA_HANDLE_SUITE', False)
        if hasattr(test_job, 'target') and test_job.target.project_settings is not None:
            project_settings = yaml.safe_load(test_job.target.project_settings) or {}
            tmp_handle_lava = project_settings.get('CI_LAVA_HANDLE_SUITE')
            if tmp_handle_lava is not None:
                handle_lava_suite = tmp_handle_lava

        definition = yaml.safe_load(data['definition'])
        if data['multinode_definition']:
            definition = yaml.safe_load(data['multinode_definition'])
        test_job.name = definition['job_name'][:255]
        job_metadata = definition.get('metadata', {})

        suite_versions = {}
        for key, value in job_metadata.items():
            if key.endswith('__version'):
                suite_versions[key.replace('__version', '')] = value
        if suite_versions:
            job_metadata['suite_versions'] = suite_versions

        results = {}
        metrics = {}
        completed = True
        if data['status'] == 'Canceled':
            # consider all canceled jobs as incomplete and discard any results
            completed = False
        else:
            for result in data['results']:
                if handle_lava_suite or result['suite'] != 'lava':
                    suite = result['suite'].split("_", 1)[-1]
                    res_name = "%s/%s" % (suite, result['name'])
                    # YAML from LAVA has all values serialized to strings
                    if result['measurement'] == 'None':
                        res_value = result['result']
                        results.update({res_name: res_value})
                    else:
                        res_value = result['measurement']
                        metrics.update({res_name: float(res_value)})
                else:
                    # add artificial 'boot' test result for each test job
                    if result['name'] == 'auto-login-action':
                        # by default the boot test is named after the device_type
                        boot = "boot-%s" % test_job.name
                        res_name = "%s/%s" % (boot, definition['device_type'])
                        res_time_name = "%s/time-%s" % (boot, definition['device_type'])
                        if 'testsuite' in job_metadata.keys():
                            # If 'testsuite' metadata key is present in the job
                            # it's appended to the test name. This way regressions can
                            # be found with more granularity
                            res_name = "%s-%s" % (res_name, job_metadata['testsuite'])
                        results.update({res_name: result['result']})
                        metrics.update({res_time_name: float(result['measurement'])})

                # Handle failed lava jobs
                if result['suite'] == 'lava' and result['name'] == 'job' and result['result'] == 'fail':
                    metadata = result['metadata']
                    test_job.failure = str(metadata)
                    test_job.save()
                    error_type = metadata.get('error_type', None)
                    # detect jobs failed because of infrastructure issues
                    if error_type in ['Infrastructure', 'Job', 'Lava']:
                        completed = False
                    # automatically resubmit in some cases
                    if error_type in ['Infrastructure', 'Job', 'Test']:
                        self.__resubmit_job__(test_job, metadata)

        return (data['status'], completed, job_metadata, results, metrics)

    def __resubmit_job__(self, test_job, metadata):
        infra_messages_re_list = []
        for message_re in self.settings.get('CI_LAVA_INFRA_ERROR_MESSAGES', []):
            try:
                r = re.compile(message_re, re.I)
                infra_messages_re_list.append(r)
            except re.error:
                # ignore incorrect expressions
                self.log_debug("'%s' is not a valid regex" % message_re)

        for regex in infra_messages_re_list:
            if regex.search(metadata['error_msg']) is not None and \
                    test_job.resubmitted_count < 3:
                resubmitted_job = self.resubmit(test_job)
                if self.settings.get('CI_LAVA_SEND_ADMIN_EMAIL', True):
                    # delay sending email by 15 seconds to allow the database object to be saved
                    send_testjob_resubmit_admin_email.apply_async(args=[test_job.pk, resubmitted_job.pk], countdown=15)
                # re-submit the job only once
                # even if there are more matches
                break

    def receive_event(self, topic, data):
        if topic.split('.')[-1] != "testjob":
            return
        lava_id = data.get('job')
        if not lava_id:
            return
        if 'sub_id' in data.keys():
            lava_id = data['sub_id']
        lava_status = data.get('state', 'Unknown')
        db_test_job_list = self.data.test_jobs.filter(
            submitted=True,
            fetched=False,
            job_id=lava_id)
        if db_test_job_list.exists() and \
                len(db_test_job_list) == 1:
            self.log_debug("interesting message received: %r" % data)
        else:
            return

        job = db_test_job_list[0]
        job.job_status = lava_status
        if lava_status == 'Finished':
            lava_health = data.get('health', 'Unknown')
            job.job_status = lava_health
        if job.name is None:
            # fetch job name once
            data = self.__get_job_details__(lava_id)
            definition = yaml.safe_load(data['definition'])
            if data['multinode_definition']:
                definition = yaml.safe_load(data['multinode_definition'])
            job.name = definition['job_name'][:255]
        job.save()
        if job.job_status in self.complete_statuses:
            self.log_info("scheduling fetch for job %s" % job.job_id)
            # introduce 2 min delay to allow LAVA for storing all results
            # this workaround should be removed once LAVA issue is fixed
            fetch.apply_async(args=[job.id], countdown=120)
