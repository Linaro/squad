from collections import defaultdict
from squad.jinja2 import register_filter


@register_filter
def filter_jobs(build):
    statuses = defaultdict(int)
    for status in build.test_jobs.values_list('job_status'):
        key = status[0] or 'Created'
        statuses[key] += 1
    filtered_jobs = [(status, statuses[status]) for status in statuses]
    return filtered_jobs
