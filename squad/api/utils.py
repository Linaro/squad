from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import CursorPagination


class DisabledHTMLFilterBackend(DjangoFilterBackend):

    def to_html(self, request, queryset, view):
        return ""


class CursorPaginationWithPageSize(CursorPagination):
    page_size_query_param = 'limit'
