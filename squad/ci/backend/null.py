import yaml
import logging


logger = logging.getLogger('squad.ci.backend')


description = "None"


class Backend(object):

    """
    This is the interface that all backends must implement. Depending on the
    actual backend, it's not mandatory to implement every method.
    """

    def __init__(self, data):
        self.data = data
        self.settings = {}
        if self.data is not None and \
                self.data.backend_settings is not None and \
                len(self.data.backend_settings) > 0:
            self.settings = yaml.safe_load(self.data.backend_settings)

    def submit(self, test_job):
        """
        Submits a given test job to the backend service.

        The return value must be list of job ids as provided by the backend.

        On errors, implementations can raise two classes of exceptions:
            * squad.ci.exceptions.SubmissionIssue, when there is an
              unrecoverable issue with the job (such as invalid data).
            * squad.ci.exceptions.TemporarySubmissionIssue, when there is a
              temporary condition that stopped the submission from happening
              that could be gone in the future (e.g. a server-side issue or a
              maintainance window).
        """
        raise NotImplementedError

    def resubmit(self, test_job):
        """
        Re-submits given test job to the backend service

        The return value must be the re-submitted job id as provided by the
        backend.

        On errors, implementations can raise two classes of exceptions:
            * squad.ci.exceptions.SubmissionIssue, when there is an
              unrecoverable issue with the job (such as invalid data).
            * squad.ci.exceptions.TemporarySubmissionIssue, when there is a
              temporary condition that stopped the submission from happening
              that could be gone in the future (e.g. a server-side issue or a
              maintainance window).
        """
        raise NotImplementedError

    def fetch(self, test_job):
        """
        Fetches data from a given test job from the backend service. It can be
        assumed that the job has been properly submited before, i.e. it has a
        proper id.

        The return value must be a tuple (status, completed, metadata, tests,
        metrics, logs), where status and logs are strings, metadata, tests and
        metrics are dictionaries, and completed is a boolean.

        On errors, implementations can raise two classes of exceptions:
            * squad.ci.exceptions.FetchIssue, when there is an unrecoverable
              issue with the job (such as an invalid job id, or something like
              that).
            * squad.ci.exceptions.TemporaryFetchIssue, when there is a
              temporary condition that prevented the job to be fetched, but
              is temporary so the test job can be fetched again in the future
              (e.g. a server-side issue or a maintainance window).
        """
        raise NotImplementedError

    def listen(self):
        """
        Listens the backend service for realtime test results. What to do with
        the received data is up to each specific backend implementation.
        """
        raise NotImplementedError

    def cancel(self, test_job):
        """
        Cancels the job if the backend allows it. It will not raise any
        exceptions even if the 'cancel' call fails. Return value should be
        True for success and False for failure.
        """
        raise NotImplementedError

    def job_url(selt, test_job):
        """
        Returns the URL of the test job in the backend
        """
        raise NotImplementedError

    def check_job_definition(selt, definition):
        """
        Returns True if job definition checks out or an error message
        """
        raise NotImplementedError

    def format_message(self, msg):
        if self.data and hasattr(self.data, "name"):
            return self.data.name + ': ' + msg
        return msg

    def log_info(self, msg):
        logger.info(self.format_message(msg))

    def log_debug(self, msg):
        logger.debug(self.format_message(msg))

    def log_warn(self, msg):
        logger.warning(self.format_message(msg))

    def log_error(self, msg):
        logger.error(self.format_message(msg))
