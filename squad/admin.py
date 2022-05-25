from django.contrib.admin import ModelAdmin
from django.utils.translation import gettext as _


class NoDeleteListingModelAdmin(ModelAdmin):
    """
    ModelAdmin without list of objects being deleted
    """
    def get_deleted_objects(self, objs, request):
        """
        Find all objects related to ``objs`` that should also be deleted. ``objs``
        must be a homogeneous iterable of objects (e.g. a QuerySet).

        Return a nested list of strings suitable for display in the
        template with the ``unordered_list`` filter.

        NOTE: this implementation just ignore generating a list of objects to be
        deleted. In some objects, there are millions of records related, and this
        wouldn't be practical to load a list of objects.

        ref: https://github.com/django/django/blob/d6aff369ad33457ae2355b5b210faf1c4890ff35/django/contrib/admin/utils.py#L103
        """
        to_delete = [_('List of objects to be deleted is disabled')]
        model_count = {}
        perms_needed = set()
        protected = []

        return to_delete, model_count, perms_needed, protected
