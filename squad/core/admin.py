from django.contrib import admin
from . import models
from .tasks import notify_project_status, postprocess_test_run
from squad.plugins import PluginLoader


class TokenAdmin(admin.ModelAdmin):
    """
    Handles global tokens, i.e. tokens that are not projec-specific.
    """
    model = models.Token
    fields = ['description', 'key']
    readonly_fields = ['key']

    def get_queryset(self, request):
        return super(TokenAdmin, self).get_queryset(request).filter(project=None)


class EnvironmentInline(admin.StackedInline):
    """
    Handles environments when editing a project.
    """
    model = models.Environment
    fields = ['slug', 'name', 'description', 'expected_test_runs']
    extra = 0


class TokenInline(admin.StackedInline):
    """
    Handles project-specific tokens inline when editing the project.
    """
    model = models.Token
    fields = ['description', 'key']
    readonly_fields = ['key']
    extra = 0


class SubscriptionInline(admin.StackedInline):
    model = models.Subscription
    fields = ['email']
    extra = 0


class AdminSubscriptionInline(admin.StackedInline):
    model = models.AdminSubscription
    fields = ['email']
    extra = 0


class ProjectAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'is_public', 'notification_strategy', 'moderate_notifications', 'custom_email_template']
    list_filter = ['group', 'is_public', 'notification_strategy', 'moderate_notifications', 'custom_email_template']
    inlines = [EnvironmentInline, TokenInline, SubscriptionInline, AdminSubscriptionInline]

    def get_form(self, request, obj=None, **kwargs):
        form = super(ProjectAdmin, self).get_form(request, obj, **kwargs)
        plugins = PluginLoader.load_all()
        form.base_fields['enabled_plugins_list'].help_text += " Available plugins:<br/><ul>" + "".join(['<li>%s</li>' % p for p in sorted(plugins.keys())]) + "</ul>"
        return form


def __resend__notification__(queryset, approve):
    for status in queryset:
        if approve:
            status.approved = True
            status.save()
        notify_project_status.delay(status.id)


def approve_project_status(modeladmin, request, queryset):
    __resend__notification__(queryset, True)


approve_project_status.short_description = "Approve and send notifications"


def resend_notification(modeladmin, request, queryset):
    __resend__notification__(queryset, False)


resend_notification.short_description = "Re-send notification"


class ProjectStatusAdmin(admin.ModelAdmin):
    model = models.ProjectStatus
    ordering = ['-build__datetime']
    list_display = ['__str__', 'finished', 'approved', 'notified']
    list_filter = ['build__project', 'finished', 'approved', 'notified']
    actions = [approve_project_status, resend_notification]

    def get_queryset(self, request):
        return super(ProjectStatusAdmin, self).get_queryset(request).prefetch_related(
            'build',
            'build__project',
            'build__project__group',
        )

    def has_add_permission(self, request):
        return False


class BuildAdmin(admin.ModelAdmin):
    model = models.Build
    ordering = ['-id']
    list_display = ['__str__', 'project']
    list_filter = ['project', 'datetime']

    def has_add_permission(self, request):
        return False


class SuiteMetadataAdmin(admin.ModelAdmin):
    models = models.SuiteMetadata
    ordering = ['name']
    list_display = ['__str__', 'kind', 'description']
    list_filter = ['kind', 'suite']
    readonly_fields = ['kind', 'suite', 'name']


class TestRunProjectFilter(admin.SimpleListFilter):
    title = "Project"
    parameter_name = "project"

    def lookups(self, request, model_admin):
        ret_list = ()
        for project in models.Project.objects.all():
            ret_list = ret_list + ((project.id, "%s/%s" % (project.group.slug, project.slug)),)
        return ret_list

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(build__project=self.value())
        return queryset


def force_execute_plugins(modeladmin, request, queryset):
    for testrun in queryset.all():
        postprocess_test_run.delay(testrun.id)


force_execute_plugins.short_description = "Postprocess selected test runs"


class TestRunAdmin(admin.ModelAdmin):
    models = models.TestRun
    list_filter = [TestRunProjectFilter]
    actions = [force_execute_plugins]

    def has_add_permission(self, request):
        return False


admin.site.register(models.Group)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.EmailTemplate)
admin.site.register(models.Token, TokenAdmin)
admin.site.register(models.ProjectStatus, ProjectStatusAdmin)
admin.site.register(models.Build, BuildAdmin)
admin.site.register(models.SuiteMetadata, SuiteMetadataAdmin)
admin.site.register(models.TestRun, TestRunAdmin)
