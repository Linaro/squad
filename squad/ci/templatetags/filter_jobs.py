from django.db.models import Count
from squad.jinja2 import register_filter


@register_filter
def filter_jobs(build):
    filtered_jobs = build.test_jobs.values_list('job_status').annotate(Count('job_status'))
    return filtered_jobs
