import json
import re
import requests
import ssl
import socket
import traceback
import yaml
import xmlrpc
import zmq

from contextlib import contextmanager
from io import BytesIO, TextIOWrapper, StringIO
from zmq.utils.strtypes import u

from xmlrpc import client as xmlrpclib
from urllib.parse import urlsplit, urljoin


from squad.ci.models import TestJob
from squad.ci.tasks import fetch, send_testjob_resubmit_admin_email
from squad.ci.exceptions import SubmissionIssue, TemporarySubmissionIssue
from squad.ci.exceptions import FetchIssue, TemporaryFetchIssue
from squad.ci.backend.null import Backend as BaseBackend


description = "LAVA"
timeout_variable_name = "TIMEOUT"
DEFAULT_TIMEOUT = 60


class RequestsTransport(xmlrpclib.SafeTransport):
    """
    Drop in Transport for xmlrpclib that uses Requests instead of http.client


    """
    # change our user agent to reflect Requests
    user_agent = "Python XMLRPC with Requests (python-requests.org)"

    def __init__(self, use_https=True, cert=None, verify=None, *args, **kwargs):
        self.cert = cert
        self.verify = verify
        self.use_https = use_https
        self.timeout = socket._GLOBAL_DEFAULT_TIMEOUT
        if 'timeout' in kwargs:
            self.timeout = kwargs.pop('timeout')

        xmlrpclib.Transport.__init__(self, *args, **kwargs)

    def request(self, host, handler, request_body, verbose):
        """
        Make an xmlrpc request.
        """
        headers = {'User-Agent': self.user_agent}
        url = self._build_url(host, handler)
        try:
            resp = requests.post(url, data=request_body, headers=headers,
                                 stream=True,
                                 cert=self.cert, verify=self.verify,
                                 timeout=self.timeout)
        except ValueError:
            raise
        except Exception:
            raise  # something went wrong
        else:
            try:
                resp.raise_for_status()
            except requests.RequestException as e:
                raise xmlrpclib.ProtocolError(url, resp.status_code,
                                              str(e), resp.headers)
            else:
                self.verbose = verbose
                return self.parse_response(resp.raw)

    def _build_url(self, host, handler):
        """
        Build a url for our request based on the host, handler and use_https
        property
        """
        scheme = 'https' if self.use_https else 'http'
        return '%s://%s/%s' % (scheme, host, handler)


class Backend(BaseBackend):

    # ------------------------------------------------------------------------
    # API implementation
    # ------------------------------------------------------------------------
    def submit(self, test_job):
        with self.handle_job_submission():
            job_id = self.__submit__(test_job.definition)
            test_job.name = self.__lava_job_name(test_job.definition)
            if isinstance(job_id, list):
                return job_id
            return [job_id]

    def cancel(self, test_job):
        if test_job.submitted and test_job.job_id is not None:
            return self.__cancel_job__(test_job.job_id)
        return False

    def fetch(self, test_job):
        try:
            data = self.__get_job_details__(test_job.job_id)
            status_key = 'status'
            if not self.use_xml_rpc:
                status_key = 'state'
            if data[status_key] in self.complete_statuses:
                data['results'] = self.__get_testjob_results_yaml__(test_job.job_id)

                # fetch logs
                raw_logs = BytesIO()
                try:
                    raw_logs = BytesIO(self.__download_full_log__(test_job.job_id))
                except Exception:
                    self.log_warn(("Logs for job %s are not available" % test_job.job_id) + "\n" + traceback.format_exc())
                return self.__parse_results__(data, test_job, raw_logs)
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
        if not listener_url:
            self.log_warn("Can't connect, no listener URL")
            if self.data is not None and hasattr(self.data, "name"):
                self.log_warn("Can't listen to %s backend" % self.data.name)

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
        self.complete_statuses = ['Complete', 'Incomplete', 'Canceled', 'Finished']
        self.__proxy__ = None
        self.use_xml_rpc = True
        url = None
        self.authentication = None
        if self.data:
            url = urlsplit(self.data.url)
        if url:
            if url.path.find("RPC2") < 0 and url.path.find("api") > 0:
                self.use_xml_rpc = False
            self.api_url_base = '%s://%s%s' % (
                url.scheme,
                url.netloc,
                url.path
            )
            # make sure URL ens with trailing slash
            if not self.api_url_base.endswith("/"):
                self.api_url_base = self.api_url_base + "/"
            self.authentication = {
                "Authorization": "Token %s" % self.data.token,
            }

    @contextmanager
    def handle_job_submission(self):
        try:
            yield
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
        except ConnectionRefusedError as fault:
            raise TemporarySubmissionIssue(str(fault))

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
            use_https = True
            if url.scheme == 'http':
                use_https = False
            proxy_timeout = self.settings.get(timeout_variable_name, DEFAULT_TIMEOUT)
            self.__proxy__ = xmlrpclib.ServerProxy(
                endpoint,
                transport=RequestsTransport(timeout=proxy_timeout, use_https=use_https)
            )
        return self.__proxy__

    def get_listener_url(self):
        url = urlsplit(self.data.url)
        hostname = url.netloc
        # remove port if exists
        hostname = hostname.split(":", 1)[0]

        socket = self.__get_publisher_event_socket__()
        if not socket:
            return None
        socket_url = urlsplit(socket)
        port = socket_url.port
        if socket_url.hostname != '*':
            hostname = socket_url.hostname
        scheme = socket_url.scheme
        return '%s://%s:%s' % (scheme, hostname, port)

    def resubmit(self, test_job):
        if test_job.job_id is None:
            return None

        with self.handle_job_submission():
            new_job_id_list = self.__resubmit__(test_job.job_id)

        if isinstance(new_job_id_list, list):
            new_job_id = new_job_id_list[0]
        else:
            new_job_id = new_job_id_list
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
        if isinstance(new_job_id_list, list) and len(new_job_id_list) > 1:
            for job_id in new_job_id_list[1:]:
                new_test_job.pk = None
                new_test_job.job_id = job_id
                new_test_job.save()
        return new_test_job

    def __cancel_job__(self, job_id):
        if self.use_xml_rpc:
            try:
                self.proxy.scheduler.cancel_job(job_id)
                return True
            except (xmlrpc.client.ProtocolError,
                    xmlrpc.client.Fault,
                    ssl.SSLError):
                return False
        else:
            response = requests.post(
                urljoin(self.api_url_base, "jobs/%s/cancel" % (job_id)),
                headers=self.authentication,
                timeout=self.settings.get(timeout_variable_name, DEFAULT_TIMEOUT)
            )
            if response.status_code == 200:
                return True

        return False

    def __lava_job_name(self, definition):
        yaml_definition = yaml.safe_load(definition)
        if 'job_name' in yaml_definition.keys():
            # only return first 255 characters
            return yaml_definition['job_name'][:255]
        return None

    def __resubmit__(self, job_id):
        if self.use_xml_rpc:
            return self.proxy.scheduler.resubmit_job(job_id)
        response = requests.post(
            urljoin(self.api_url_base, "jobs/%s/resubmit" % (job_id)),
            headers=self.authentication,
            timeout=self.settings.get(timeout_variable_name, DEFAULT_TIMEOUT)
        )
        if response.status_code == 201:
            return response.json()['job_ids']
        return []

    def __submit__(self, definition):
        if self.use_xml_rpc:
            return self.proxy.scheduler.submit_job(definition)
        response = requests.post(
            urljoin(self.api_url_base, "jobs/"),
            headers=self.authentication,
            data={"definition": definition},
            timeout=self.settings.get(timeout_variable_name, DEFAULT_TIMEOUT)
        )
        if response.status_code == 201:
            return response.json()['job_ids']
        return []

    def __get_job_details__(self, job_id):
        if self.use_xml_rpc:
            return self.proxy.scheduler.job_details(job_id)
        response = requests.get(
            urljoin(self.api_url_base, "jobs/%s" % (job_id)),
            headers=self.authentication,
            timeout=self.settings.get(timeout_variable_name, DEFAULT_TIMEOUT)
        )
        if response.status_code == 200:
            return response.json()
        raise FetchIssue(response.text)

    def __download_full_log__(self, job_id):
        response = None
        if self.use_xml_rpc:
            url = self.data.url.replace('/RPC2', '/scheduler/job/%s/log_file/plain' % job_id)
            payload = {"user": self.data.username, "token": self.data.token}
            try:
                response = requests.get(
                    url,
                    params=payload,
                    timeout=self.settings.get(timeout_variable_name, DEFAULT_TIMEOUT)
                )

            except requests.exceptions.RequestException:
                self.log_error("Unable to download log for {backend_name}/{job_id}".format(backend_name=self.data.name, job_id=job_id))
        else:
            try:
                response = requests.get(
                    urljoin(self.api_url_base, "jobs/%s/logs/" % (job_id)),
                    headers=self.authentication,
                    timeout=self.settings.get(timeout_variable_name, DEFAULT_TIMEOUT)
                )
            except requests.exceptions.RequestException:
                self.log_error("Unable to download log for {backend_name}/{job_id}".format(backend_name=self.data.name, job_id=job_id))
        if response and response.status_code == 200:
            return response.content
        return b''

    def __download_test_log__(self, raw_log, log_start, log_end):
        if not log_start:
            return ""

        return_lines = StringIO()
        log_start_line = int(log_start)
        log_end_line = None
        if log_end:
            log_end_line = int(log_end)
        else:
            log_end_line = log_start_line + 2  # LAVA sometimes misses the signals
        raw_log.seek(0)
        counter = 0
        for line in raw_log:
            counter += 1
            if counter < log_start_line:
                continue
            try:
                return_lines.write(line.decode("utf-8"))
            except UnicodeDecodeError:
                return_lines.write(line.decode("iso-8859-1"))
            return_lines.write("\n")
            if counter >= log_end_line:
                break
        raw_log.seek(0)
        return return_lines.getvalue()

    def __parse_log__(self, log_data):
        returned_log = StringIO()
        start_dict = False
        tmp_dict = None
        tmp_key = None
        is_value = False
        self.log_debug("Length of log buffer: %s" % log_data.getbuffer().nbytes)
        if log_data.getbuffer().nbytes > 0:
            try:
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
                                            returned_log.write(tmp_dict["msg"].decode('latin-1', 'ignore') + "\n")
                                        except ValueError:
                                            # despite ignoring errors, they are still raised sometimes
                                            pass
                                    else:
                                        returned_log.write(tmp_dict['msg'] + "\n")
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
            except (yaml.scanner.ScannerError, yaml.parser.ParserError):
                log_data.seek(0)
                wrapper = TextIOWrapper(log_data, encoding='utf-8')
                self.log_error("Problem parsing LAVA log\n" + wrapper.read() + "\n" + traceback.format_exc())

        return returned_log.getvalue()

    def __get_testjob_results_yaml__(self, job_id):
        self.log_debug("Retrieving result summary for job: %s" % job_id)
        lava_job_results = []
        if self.use_xml_rpc:
            suites = self.proxy.results.get_testjob_suites_list_yaml(job_id)
            y = yaml.safe_load(suites)
            for suite in y:
                limit = 500
                offset = 0
                while True:
                    self.log_debug(
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
        else:
            suites_resp = requests.get(
                urljoin(self.api_url_base, "jobs/%s/suites/" % (job_id)),
                headers=self.authentication,
                timeout=self.settings.get(timeout_variable_name, DEFAULT_TIMEOUT)
            )
            while suites_resp.status_code == 200:
                suites_content = suites_resp.json()
                for suite in suites_content['results']:
                    tests_resp = requests.get(
                        urljoin(self.api_url_base, "jobs/%s/suites/%s/tests" % (job_id, suite['id'])),
                        headers=self.authentication,
                        timeout=self.settings.get(timeout_variable_name, DEFAULT_TIMEOUT)
                    )
                    while tests_resp.status_code == 200:
                        tests_content = tests_resp.json()
                        for test in tests_content['results']:
                            test['suite'] = suite['name']
                        lava_job_results = lava_job_results + tests_content['results']
                        if tests_content['next']:
                            tests_resp = requests.get(
                                tests_content['next'],
                                headers=self.authentication,
                                timeout=self.settings.get(timeout_variable_name, DEFAULT_TIMEOUT)
                            )
                        else:
                            break
                if suites_content['next']:
                    suites_resp = requests.get(
                        suites_content['next'],
                        headers=self.authentication,
                        timeout=self.settings.get(timeout_variable_name, DEFAULT_TIMEOUT)
                    )
                else:
                    break

        return lava_job_results

    def __get_publisher_event_socket__(self):
        if self.use_xml_rpc:
            return self.proxy.scheduler.get_publisher_event_socket()
        lava_resp = requests.get(
            urljoin(self.api_url_base, "system/master_config/"),
            timeout=self.settings.get(timeout_variable_name, DEFAULT_TIMEOUT)
        )
        if lava_resp.status_code == 200:
            return lava_resp.json()['EVENT_SOCKET']
        # should there be an exception if status_code is != 200 ?
        return None

    def __resolve_settings__(self, test_job):
        result_settings = self.settings
        if getattr(test_job, 'target', None) is not None \
                and test_job.target.project_settings is not None:
            ps = yaml.safe_load(test_job.target.project_settings) or {}
            result_settings.update(ps)
        return result_settings

    def __parse_results__(self, data, test_job, raw_logs):
        project_settings = self.__resolve_settings__(test_job)
        handle_lava_suite = project_settings.get('CI_LAVA_HANDLE_SUITE', False)
        handle_lava_boot = project_settings.get('CI_LAVA_HANDLE_BOOT', False)
        clone_measurements_to_tests = project_settings.get('CI_LAVA_CLONE_MEASUREMENTS', False)
        ignore_infra_errors = project_settings.get('CI_LAVA_WORK_AROUND_INFRA_ERRORS', False)

        definition = yaml.safe_load(data['definition'])
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
        status_key = 'status'
        if not self.use_xml_rpc:
            status_key = 'health'

        if data[status_key] == 'Canceled':
            # consider all canceled jobs as incomplete and discard any results
            completed = False
        else:
            for result in data['results']:
                if handle_lava_suite or result['suite'] != 'lava':
                    suite = result['suite'].split("_", 1)[-1]
                    res_name = "%s/%s" % (suite, result['name'])
                    res_log = None
                    if 'log_start_line' in result.keys() and \
                            'log_end_line' in result.keys() and \
                            result['log_start_line'] is not None and \
                            result['log_end_line'] is not None:
                        res_log = self.__download_test_log__(raw_logs, result['log_start_line'], result['log_end_line'])
                    # YAML from LAVA has all values serialized to strings
                    if result['measurement'] == 'None' or result['measurement'] is None:
                        res_value = result['result']
                        results.update({res_name: {'result': res_value, 'log': res_log}})
                    else:
                        res_value = result['measurement']
                        try:
                            unit = result['unit']
                        except KeyError:
                            # work around the bug in LAVA
                            # https://git.lavasoftware.org/lava/lava/-/issues/449
                            unit = result.get('units', 'items')
                        metrics.update({res_name: {'value': float(res_value), 'unit': unit}})
                        if clone_measurements_to_tests:
                            res_value = result['result']
                            results.update({res_name: res_value})
                elif result['name'] == 'auto-login-action' and handle_lava_boot:
                    # add artificial 'boot' test result for each test job
                    # by default the boot test is named after the device_type
                    boot = "boot-%s" % test_job.name
                    res_name = "%s/%s" % (boot, definition['device_type'])
                    res_time_name = "%s/time-%s" % (boot, definition['device_type'])
                    if 'testsuite' in job_metadata.keys():
                        # If 'testsuite' metadata key is present in the job
                        # it's appended to the test name. This way regressions can
                        # be found with more granularity
                        res_name = "%s-%s" % (res_name, job_metadata['testsuite'])
                    try:
                        unit = result['unit']
                    except KeyError:
                        # work around the bug in LAVA
                        # https://git.lavasoftware.org/lava/lava/-/issues/449
                        unit = result.get('units', 'items')
                    results.update({res_name: result['result']})
                    metrics.update({res_time_name: {'value': float(result['measurement']), 'unit': unit}})

                # Handle failed lava jobs
                if result['suite'] == 'lava' and result['name'] == 'job' and result['result'] == 'fail':
                    metadata = result['metadata']
                    if isinstance(metadata, str):
                        metadata = yaml.safe_load(metadata)
                    test_job.failure = str(metadata)
                    test_job.save()
                    error_type = metadata.get('error_type', None)
                    # detect jobs failed because of infrastructure issues
                    if error_type in ['Infrastructure', 'Job', 'Lava']:
                        if not ignore_infra_errors:
                            completed = False
                    # automatically resubmit in some cases
                    if error_type in ['Infrastructure', 'Job', 'Test']:
                        self.__resubmit_job__(test_job, metadata)
        return (data[status_key], completed, job_metadata, results, metrics, self.__parse_log__(raw_logs))

    def __resubmit_job__(self, test_job, metadata):
        infra_messages_re_list = []
        project_settings = self.__resolve_settings__(test_job)
        error_messages_settings = project_settings.get('CI_LAVA_INFRA_ERROR_MESSAGES', [])
        for message_re in error_messages_settings:
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
                if project_settings.get('CI_LAVA_SEND_ADMIN_EMAIL', True):
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
            job.name = definition['job_name'][:255]
        job.save()
        if job.job_status in self.complete_statuses:
            self.log_info("scheduling fetch for job %s" % job.job_id)
            fetch.apply_async(args=[job.id])
