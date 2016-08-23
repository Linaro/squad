from django.contrib import admin
from . import models


class TokenInline(admin.StackedInline):
    model = models.Token
    fields = ['description', 'key']
    readonly_fields = ['key']
    extra = 0


class ProjectAdmin(admin.ModelAdmin):
    inlines = [TokenInline]


admin.site.register(models.Group)
admin.site.register(models.Project, ProjectAdmin)
