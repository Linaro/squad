from django import template
from django.db.models import Count


register = template.Library()


@register.filter
def filter_jobs(build):
    filtered_jobs = build.test_jobs.values_list('job_status').annotate(Count('job_status'))
    return filtered_jobs
