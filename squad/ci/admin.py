from django.contrib import admin
from squad.ci.models import Backend, TestJob
from squad.ci.tasks import submit, fetch, poll


def poll_backends(modeladmin, request, queryset):
    for backend in queryset:
        poll.delay(backend.id)


poll_backends.short_description = "Poll selected backends"


class BackendAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'implementation_type')
    actions = [poll_backends]


def submit_job(modeladmin, request, queryset):
    for test_job in queryset:
        submit.delay(test_job.id)


submit_job.short_description = 'Submit selected test jobs'


def fetch_job(modeladmin, request, queryset):
    for test_job in queryset:
        fetch.delay(test_job.id)


fetch_job.short_description = 'Fetch results of the selected test jobs'


class TestJobAdmin(admin.ModelAdmin):
    list_display = ('backend', 'target', 'submitted', 'fetched', 'success', 'last_fetch_attempt', 'job_id',)
    list_filter = ('backend', 'target', 'submitted', 'fetched')
    actions = [submit_job, fetch_job]


admin.site.register(Backend, BackendAdmin)
admin.site.register(TestJob, TestJobAdmin)
