def task_id(testjob):
    return "%d:%s/%s" % (testjob.id, testjob.backend.name, testjob.job_id)
