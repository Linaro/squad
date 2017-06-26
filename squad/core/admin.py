from django.contrib import admin
from . import models
from .tasks import notify_project


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
    readonly_fields = ['slug']
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
    fields = ['email', 'html']
    extra = 0


def force_notify_project(modeladmin, request, queryset):
    for project in queryset:
        notify_project.delay(project.pk)


force_notify_project.short_description = "Force sending email notification for selected projects"


class ProjectAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'is_public', 'notification_strategy']
    inlines = [EnvironmentInline, TokenInline, SubscriptionInline]
    actions = [force_notify_project]


class ProjectStatusAdmin(admin.ModelAdmin):
    model = models.ProjectStatus


admin.site.register(models.Group)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.Token, TokenAdmin)
admin.site.register(models.ProjectStatus, ProjectStatusAdmin)
