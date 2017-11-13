import json
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
LAVA_INFRA_ERROR_MESSAGES = [
    'Connection closed',
    'lava_test_shell connection dropped.',
    'fastboot-flash-action timed out',
    'auto-login-action timed out']


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
            raise TemporarySubmissionIssue(str(error))
        except xmlrpc.client.Fault as fault:
            if fault.faultCode // 100 == 5:
                # assume HTTP errors 5xx are temporary issues
                raise TemporarySubmissionIssue(str(fault))
            else:
                raise SubmissionIssue(str(fault))

    def fetch(self, test_job):
        try:
            data = self.__get_job_details__(test_job.job_id)

            if data['status'] in self.complete_statuses:
                yamldata = self.__get_testjob_results_yaml__(test_job.job_id)
                data['results'] = yaml.load(yamldata, Loader=yaml.CLoader)

                # fetch logs
                logs = ""
                try:
                    logs = self.__get_job_logs__(test_job.job_id)
                except Exception:
                    self.log_warn(("Logs for job %s are not available" % test_job.job_id) + "\n" + traceback.format_exc())

                return self.__parse_results__(data, test_job) + (logs,)
        except xmlrpc.client.ProtocolError as error:
            raise TemporaryFetchIssue(str(error))
        except xmlrpc.client.Fault as fault:
            if fault.faultCode // 100 == 5:
                # assume HTTP errors 5xx are temporary issues
                raise TemporaryFetchIssue(str(fault))
            else:
                raise FetchIssue(str(fault))

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
                self.log_debug("message received: %r" % message)
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
                testrun=test_job.testrun,
                definition=test_job.definition,
                target=test_job.target,
                build=test_job.build,
                environment=test_job.environment,
                submitted=True,
                job_id=new_job_id,
                resubmitted_count=test_job.resubmitted_count + 1,
                name=new_test_job_name,
            )
            test_job.can_resubmit = False
            test_job.save()
            new_test_job.save()
            return new_test_job
        return None

    def __lava_job_name(self, definition):
        yaml_definition = yaml.load(definition)
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

    def __get_job_logs__(self, job_id):
        # Fetching logs is currently being a problem with regards to memory
        # usage, so we will just not do it for now.
        return None

        log_data = self.proxy.scheduler.job_output(job_id).data.decode('utf-8')
        log_data_yaml = yaml.load(log_data, Loader=yaml.CLoader)
        returned_log = ""
        for log_entry in log_data_yaml:
            if log_entry['lvl'] == 'target':
                if isinstance(log_entry['msg'], bytes):
                    try:
                        # seems like latin-1 is the encoding used by serial
                        # this might not be true in all cases
                        returned_log += log_entry["msg"].decode('latin-1', 'ignore')
                    except ValueError:
                        # despite ignoring errors, they are still raised sometimes
                        pass
                else:
                    # this should be string in all other cases
                    returned_log += log_entry["msg"]
                returned_log += "\n"
        return returned_log

    def __get_testjob_results_yaml__(self, job_id):
        return self.proxy.results.get_testjob_results_yaml(job_id)

    def __get_publisher_event_socket__(self):
        return self.proxy.scheduler.get_publisher_event_socket()

    def __parse_results__(self, data, test_job):
        if data['is_pipeline'] is False:
            # in case of v1 job, return empty data
            return (data['status'], {}, {}, {})
        definition = yaml.load(data['definition'])
        if data['multinode_definition']:
            definition = yaml.load(data['multinode_definition'])
        test_job.name = definition['job_name'][:255]
        job_metadata = definition['metadata']
        results = {}
        metrics = {}
        completed = True
        if data['status'] == 'Canceled':
            # consider all canceled jobs as incomplete and discard any results
            completed = False
        else:
            for result in data['results']:
                if result['suite'] != 'lava':
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
                        res_name = "boot/%s" % (definition['device_type'])
                        res_time_name = "boot/time-%s" % (definition['device_type'])
                        if 'testsuite' in job_metadata.keys():
                            # If 'testsuite' metadata key is present in the job
                            # it's appended to the test name. This way regressions can
                            # be found with more granularity
                            res_name = "%s-%s" % (res_name, job_metadata['testsuite'])
                        results.update({res_name: result['result']})
                        metrics.update({res_time_name: float(result['measurement'])})
                    if result['name'] == 'job' and result['result'] == 'fail':
                        metadata = result['metadata']
                        test_job.failure = str(metadata)
                        test_job.save()
                        # detect jobs failed because of infrastructure issues
                        if metadata['error_type'] in ['Infrastructure', 'Lava', 'Job']:
                            completed = False
                        # automatically resubmit in some cases
                        if metadata['error_type'] == 'Infrastructure' and \
                                any(substring.lower() in metadata['error_msg'].lower() for substring in LAVA_INFRA_ERROR_MESSAGES):
                            if test_job.resubmitted_count < 3:
                                resubmitted_job = self.resubmit(test_job)
                                # delay sending email by 15 seconds to allow the database object to be saved
                                send_testjob_resubmit_admin_email.apply_async(args=[test_job.pk, resubmitted_job.pk], countdown=15)
                                # don't send admin_email
                                continue

        return (data['status'], completed, job_metadata, results, metrics)

    def receive_event(self, topic, data):
        if topic.split('.')[-1] != "testjob":
            return
        lava_id = data.get('job')
        if not lava_id:
            return
        if 'sub_id' in data.keys():
            lava_id = data['sub_id']
        lava_status = data['status']
        db_test_job_list = self.data.test_jobs.filter(
            submitted=True,
            fetched=False,
            job_id=lava_id)
        if db_test_job_list.exists() and \
                len(db_test_job_list) == 1:
            job = db_test_job_list[0]
            job.job_status = lava_status
            if job.name is None:
                # fetch job name once
                data = self.__get_job_details__(lava_id)
                if data['is_pipeline'] is False:
                    return
                definition = yaml.load(data['definition'])
                if data['multinode_definition']:
                    definition = yaml.load(data['multinode_definition'])
                job.name = definition['job_name'][:255]
            job.save()
            if lava_status in self.complete_statuses:
                self.log_info("scheduling fetch for job %s" % job.job_id)
                # introduce 2 min delay to allow LAVA for storing all results
                # this workaround should be removed once LAVA issue is fixed
                fetch.apply_async(args=[job.id], countdown=120)
