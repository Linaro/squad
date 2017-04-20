class SubmissionIssue(Exception):
    retry = False


class TemporarySubmissionIssue(SubmissionIssue):
    retry = True
