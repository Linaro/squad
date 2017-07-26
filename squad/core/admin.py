from django.contrib import admin
from . import models
from .tasks import notify_project, notify_project_status


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


def force_notify_project(modeladmin, request, queryset):
    for project in queryset:
        notify_project.delay(project.pk)


force_notify_project.short_description = "Force sending email notification for selected projects"


class ProjectAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'is_public', 'notification_strategy', 'moderate_notifications']
    list_filter = ['group', 'is_public', 'notification_strategy', 'moderate_notifications']
    inlines = [EnvironmentInline, TokenInline, SubscriptionInline, AdminSubscriptionInline]
    actions = [force_notify_project]


def approve_project_status(modeladmin, request, queryset):
    for status in queryset:
        status.approved = True
        status.save()
        notify_project_status.delay(status.id)


approve_project_status.short_description = "Approve and send notifications"


class ProjectStatusAdmin(admin.ModelAdmin):
    model = models.ProjectStatus
    list_display = ['__str__', 'approved', 'notified']
    list_filter = ['build__project', 'approved', 'notified']
    actions = [approve_project_status]

    def get_queryset(self, request):
        return super(ProjectStatusAdmin, self).get_queryset(request).prefetch_related(
            'build',
            'build__project',
            'build__project__group',
        )


admin.site.register(models.Group)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.Token, TokenAdmin)
admin.site.register(models.ProjectStatus, ProjectStatusAdmin)
