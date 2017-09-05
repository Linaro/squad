class SubmissionIssue(Exception):
    retry = False


class TemporarySubmissionIssue(SubmissionIssue):
    retry = True


class FetchIssue(Exception):
    retry = False


class TemporaryFetchIssue(FetchIssue):
    retry = True
