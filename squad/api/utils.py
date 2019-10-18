from squad.compat import RestFrameworkFilterBackend
from rest_framework.pagination import CursorPagination


class DisabledHTMLFilterBackend(RestFrameworkFilterBackend):

    def to_html(self, request, queryset, view):
        return ""


class CursorPaginationWithPageSize(CursorPagination):
    page_size_query_param = 'limit'
