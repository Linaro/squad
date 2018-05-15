from django_filters.rest_framework import DjangoFilterBackend


class DisabledHTMLFilterBackend(DjangoFilterBackend):

    def to_html(self, request, queryset, view):
        return ""
