from django.core.exceptions import PermissionDenied
from django.shortcuts import render_to_response


class Custom401Middleware(object):
    def process_exception(self, request, exception):
        if isinstance(exception, PermissionDenied):
            return render_to_response(
                "401.html",
                {'request': request},
                status=401)
        return None
