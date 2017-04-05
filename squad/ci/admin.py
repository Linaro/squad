from django.contrib import admin
from squad.ci.models import Backend, TestJob
from squad.ci.tasks import submit, fetch


class BackendAdmin(admin.ModelAdmin):
    list_display = ('url', 'implementation_type')


def submit_job(modeladmin, request, queryset):
    for test_job in queryset:
        submit.delay(test_job.id)


submit_job.short_description = 'Submit selected test jobs'


def fetch_job(modeladmin, request, queryset):
    for test_job in queryset:
        fetch.delay(test_job.id)


fetch_job.short_description = 'Fetch results of the selected test jobs'


class TestJobAdmin(admin.ModelAdmin):
    list_display = ('backend', 'target', 'submitted', 'fetched', 'job_id')
    list_filter = ('submitted', 'fetched')
    actions = [submit_job, fetch_job]


admin.site.register(Backend, BackendAdmin)
admin.site.register(TestJob, TestJobAdmin)
