from django.contrib import admin
from . import models


class TokenAdmin(admin.ModelAdmin):
    """
    Handles global tokens, i.e. tokens that are not projec-specific.
    """
    model = models.Token
    fields = ['description', 'key']
    readonly_fields = ['key']

    def get_queryset(self, request):
        return super(TokenAdmin, self).get_queryset(request).filter(project=None)


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


class ProjectAdmin(admin.ModelAdmin):
    inlines = [TokenInline, SubscriptionInline]


admin.site.register(models.Group)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.Token, TokenAdmin)
