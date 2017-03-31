from django.contrib import admin
from squad.ci.models import Backend, TestJob


class BackendAdmin(admin.ModelAdmin):
    list_display = ('url', 'implementation_type')


class TestJobAdmin(admin.ModelAdmin):
    list_filter = ('submitted', 'fetched')


admin.site.register(Backend, BackendAdmin)
admin.site.register(TestJob, TestJobAdmin)
