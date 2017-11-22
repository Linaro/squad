from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
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


class TestJobFailureFilter(admin.SimpleListFilter):

    title = _('Failed')

    parameter_name = 'failed'

    def lookups(self, request, model_admin):
        return (
            ('yes', _('Yes')),
            ('no', _('No')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(failure=None)
        if self.value() == 'no':
            return queryset.filter(failure=None)
        return queryset


class TestJobAdmin(admin.ModelAdmin):
    list_display = ('backend', 'target', 'submitted', 'fetched', 'success', 'last_fetch_attempt', 'job_id_link',)
    list_filter = ('backend', 'target', 'submitted', 'fetched', TestJobFailureFilter)
    readonly_fields = ('testrun', 'target_build',)
    actions = [submit_job, fetch_job]

    def job_id_link(self, test_job):
        return '<a href="%s">%s</a>' % (test_job.url, test_job.job_id)
    job_id_link.allow_tags = True
    job_id_link.short_description = 'Job ID ⇒'


admin.site.register(Backend, BackendAdmin)
admin.site.register(TestJob, TestJobAdmin)
