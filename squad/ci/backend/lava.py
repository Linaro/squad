import json
import yaml
import xmlrpc
import zmq

from zmq.utils.strtypes import u

from xmlrpc import client as xmlrpclib
from urllib.parse import urlsplit


from squad.ci.exceptions import SubmissionIssue, TemporarySubmissionIssue
from squad.ci.backend.null import Backend as BaseBackend

description = "LAVA"


class MetadataParser(object):

    def __init__(self, definition):
        self.definition = definition
        self.metadata = {}
        self.__extract_metadata_recursively__(self.definition)

    def __extract_metadata_recursively__(self, data):
        if isinstance(data, dict):
            for key in data:
                if key == 'metadata':
                    for k in data[key]:
                        self.metadata[k] = data[key][k]
                else:
                    self.__extract_metadata_recursively__(data[key])
        elif isinstance(data, list):
            for item in data:
                self.__extract_metadata_recursively__(item)


class Backend(BaseBackend):

    # ------------------------------------------------------------------------
    # API implementation
    # ------------------------------------------------------------------------
    def submit(self, test_job):
        try:
            job_id = self.__submit__(test_job.definition)
            return job_id
        except xmlrpc.client.Fault as fault:
            if fault.faultCode // 100 == 5:
                # assume HTTP errors 5xx are temporary issues
                raise TemporarySubmissionIssue(str(fault))
            else:
                raise SubmissionIssue(str(fault))

    def fetch(self, test_job):
        data = self.__get_job_details__(test_job.job_id)
        if data['status'] in self.complete_statuses:
            yamldata = self.__get_testjob_results_yaml__(test_job.job_id)
            data['results'] = yaml.load(yamldata)
            return self.__parse_results__(data)

    def listen(self):
        if self.data.listener_url:
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.SUB)
            # TODO: there might be an issue with setsockopt_string depending on
            # python version. This might need refactoring
            socket_filter = ""
            if self.data.listener_filter:
                socket_filter = self.data.listener_filter
            self.socket.setsockopt_string(zmq.SUBSCRIBE, socket_filter)
            self.socket.connect(self.data.listener_url)

            while True:
                try:
                    message = self.socket.recv_multipart()
                    (topic, uuid, dt, username, data) = (u(m) for m in message[:])
                    lava_id = data['job']
                    if 'sub_id' in data.keys():
                        lava_id = data['sub_id']
                    lava_status = data['status']
                    if lava_status in self.complete_statuses:
                        db_test_job_list = self.data.test_jobs.filter(
                            submitted=True,
                            fetched=False,
                            job_id=lava_id)
                        if db_test_job_list.exists() and \
                                len(db_test_job_list) == 1:
                            self.data.fetch(db_test_job_list[0])
                except Exception as e:
                    # TODO: at least log error
                    pass

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

    def __submit__(self, definition):
        return self.proxy.scheduler.submit_job(definition)

    def __get_job_details__(self, job_id):
        return self.proxy.scheduler.job_details(job_id)

    def __get_testjob_results_yaml__(self, job_id):
        return self.proxy.results.get_testjob_results_yaml(job_id)

    def __parse_results__(self, data):
        if data['is_pipeline'] is False:
            # in case of v1 job, return empty data
            return (data['status'], {}, {}, {})
        definition = yaml.load(data['definition'])
        if data['multinode_definition']:
            definition = yaml.load(data['multinode_definition'])
        mp = MetadataParser(definition)
        results = {}
        metrics = {}
        for result in data['results']:
            if result['suite'] != 'lava':
                suite = result['suite'].split("_", 1)[1]
                res_name = "%s/%s" % (suite, result['name'])
                # YAML from LAVA has all values serialized to strings
                if result['measurement'] == 'None':
                    res_value = result['result']
                    results.update({res_name: res_value})
                else:
                    res_value = result['measurement']
                    metrics.update({res_name: res_value})
        return (data['status'], mp.metadata, results, metrics)
