from squad.compat import RestFrameworkFilterBackend
from rest_framework.pagination import CursorPagination
from rest_framework.renderers import BrowsableAPIRenderer


class DisabledHTMLFilterBackend(RestFrameworkFilterBackend):

    def to_html(self, request, queryset, view):
        return ""


class CursorPaginationWithPageSize(CursorPagination):
    page_size_query_param = 'limit'
    ordering = '-id'


# ref: https://bradmontgomery.net/blog/disabling-forms-django-rest-frameworks-browsable-api/
class BrowsableAPIRendererWithoutForms(BrowsableAPIRenderer):
    """Renders the browsable api, but excludes the forms."""

    def get_context(self, *args, **kwargs):
        ctx = super().get_context(*args, **kwargs)
        ctx['display_edit_forms'] = False
        return ctx

    def show_form_for_method(self, view, method, request, obj):
        """We never want to do this! So just return False."""
        return False

    def get_rendered_html_form(self, data, view, method, request):
        """Why render _any_ forms at all. This method should return
        rendered HTML, so let's simply return an empty string.
        """
        return ""
