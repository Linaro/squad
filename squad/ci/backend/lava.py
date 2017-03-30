import yaml
from xmlrpc import client as xmlrpclib
from urllib.parse import urlsplit


from squad.ci.backend.null import Backend as BaseBackend


description = "LAVA"


class Backend(BaseBackend):

    # ------------------------------------------------------------------------
    # API implementation
    # ------------------------------------------------------------------------
    def submit(self, test_job):
        job_id = self.__submit__(test_job.definition)
        return job_id

    def fetch(self, test_job):
        data = self.__get_job_details__(test_job.job_id)
        if data['status'] in ['Complete', 'Incomplete', 'Canceled']:
            yamldata = self.__get_testjob_results_yaml__(test_job.job_id)
            data['results'] = yaml.load(yamldata)
        return self.__parse_results__(data)

    def listen(self):
        pass  # TODO

    # ------------------------------------------------------------------------
    # implementation details
    # ------------------------------------------------------------------------
    def __init__(self, data):
        super(Backend, self).__init__(data)
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
        return (data['status'], {}, {}, {})
