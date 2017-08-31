from django.contrib import admin
from . import models
from .tasks import notify_project_status


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
    fields = ['slug', 'name', 'expected_test_runs']
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
    list_display = ['__str__', 'approved', 'notified']
    list_filter = ['build__project', 'approved', 'notified']
    actions = [approve_project_status, resend_notification]

    def get_queryset(self, request):
        return super(ProjectStatusAdmin, self).get_queryset(request).prefetch_related(
            'build',
            'build__project',
            'build__project__group',
        )


class BuildAdmin(admin.ModelAdmin):
    model = models.Build
    ordering = ['-id']
    list_display = ['__str__', 'project']
    list_filter = ['project', 'datetime']


admin.site.register(models.Group)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.EmailTemplate)
admin.site.register(models.Token, TokenAdmin)
admin.site.register(models.ProjectStatus, ProjectStatusAdmin)
admin.site.register(models.Build, BuildAdmin)
