from django import forms
from django.contrib import admin
from django.forms import ModelForm, ModelMultipleChoiceField, CheckboxSelectMultiple
from simple_history.admin import SimpleHistoryAdmin
from django.contrib.admin.models import LogEntry, DELETION
from django.utils.html import escape
from django.urls import reverse
from django.utils.safestring import mark_safe


from . import models
from .tasks import postprocess_test_run
from .tasks.notification import notify_project_status
from squad.admin import NoDeleteListingModelAdmin


class GroupMemberAdmin(admin.TabularInline):
    """
    Handles group members
    """
    model = models.GroupMember

    readonly_fields = ['member_since']


class GroupAdmin(NoDeleteListingModelAdmin):
    """
    Handles groups
    """
    model = models.Group
    inlines = [GroupMemberAdmin]


class EnvironmentInline(admin.StackedInline):
    """
    Handles environments when editing a project.
    """
    model = models.Environment
    fields = ['slug', 'name', 'description', 'expected_test_runs']
    extra = 0


class SubscriptionInline(admin.StackedInline):
    model = models.Subscription
    fields = ['email', 'user', 'notification_strategy']
    extra = 0


class AdminSubscriptionInline(admin.StackedInline):
    model = models.AdminSubscription
    fields = ['email']
    extra = 0


class ProjectAdmin(NoDeleteListingModelAdmin):
    list_display = ['__str__', 'is_public', 'moderate_notifications', 'custom_email_template']
    list_filter = ['group', 'is_public', 'moderate_notifications', 'custom_email_template']
    inlines = [EnvironmentInline, SubscriptionInline, AdminSubscriptionInline]
    save_as = True


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
    list_display = ['__str__', 'finished', 'approved', 'notified', 'tests_total', 'tests_pass', 'tests_fail', 'tests_skip', 'tests_xfail']
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


class BuildAdmin(NoDeleteListingModelAdmin):
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


class TestRunAdmin(NoDeleteListingModelAdmin):
    models = models.TestRun
    list_filter = [TestRunProjectFilter]
    actions = [force_execute_plugins]

    def has_add_permission(self, request):
        return False


class PatchSourceForm(ModelForm):
    password = forms.CharField(max_length=128, required=False)

    def __init__(self, *args, **kwargs):
        super(PatchSourceForm, self).__init__(*args, **kwargs)
        self.initial['password'] = self.instance.password

    class Meta:
        model = models.PatchSource
        fields = ['name', 'url', 'username', 'password', 'token', 'implementation']


class PatchSourceAdmin(admin.ModelAdmin):
    form = PatchSourceForm

    def save_model(self, request, obj, form, change):
        if 'password' in form.changed_data:
            obj.password = form.cleaned_data['password']
        super(PatchSourceAdmin, self).save_model(request, obj, form, change)


class SelectEnvironment(ModelMultipleChoiceField):

    def label_from_instance(self, e):
        return e.project.full_name + ' - ' + e.slug


class KnownIssueAdminForm(ModelForm):
    environments = SelectEnvironment(
        models.Environment.objects.prefetch_related('project', 'project__group').order_by('project__group__slug', 'project__slug'),
        widget=CheckboxSelectMultiple,
    )

    class Meta:
        model = models.KnownIssue
        fields = "__all__"


class KnownIssueGroupFilter(admin.SimpleListFilter):

    title = 'group'
    parameter_name = 'group'

    def lookups(self, request, model_admin):
        return ((g.id, g.slug) for g in models.Group.objects.order_by('slug').all())

    def queryset(self, request, queryset):
        group = request.GET.get('group')
        if group:
            return queryset.filter(environments__project__group__id=group).distinct()
        else:
            return queryset


class KnownIssueAdmin(admin.ModelAdmin):
    models = models.KnownIssue
    list_display = ['title', 'url', 'active', 'intermittent']
    list_filter = [KnownIssueGroupFilter]
    form = KnownIssueAdminForm


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    date_hierarchy = 'action_time'

    list_filter = [
        'user',
        'content_type',
        'action_flag'
    ]

    search_fields = [
        'object_repr',
        'change_message'
    ]

    list_display = [
        'action_time',
        'user',
        'content_type',
        'object_link',
        'action_flag',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def object_link(self, obj):
        if obj.action_flag == DELETION:
            link = escape(obj.object_repr)
        else:
            ct = obj.content_type
            link = '<a href="%s">%s</a>' % (
                reverse('admin:%s_%s_change' % (ct.app_label, ct.model), args=[obj.object_id]),
                escape(obj.object_repr),
            )
        return mark_safe(link)
    object_link.admin_order_field = "object_repr"
    object_link.short_description = "object"


admin.site.register(models.Group, GroupAdmin)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.EmailTemplate, SimpleHistoryAdmin)
admin.site.register(models.ProjectStatus, ProjectStatusAdmin)
admin.site.register(models.Build, BuildAdmin)
admin.site.register(models.SuiteMetadata, SuiteMetadataAdmin)
admin.site.register(models.TestRun, TestRunAdmin)
admin.site.register(models.PatchSource, PatchSourceAdmin)
admin.site.register(models.KnownIssue, KnownIssueAdmin)
