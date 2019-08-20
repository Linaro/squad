"""
Copyright (c) 2013-2015 Philip Neustrom <philipn@gmail.com>,
2016-2017 Ryan P Kilby <rpkilby@ncsu.edu>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is furnished
to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

This piece of code was copied from master branch of
https://github.com/philipn/django-rest-framework-filters

SQUAD currently uses version 0.10.2 which doesn't have the required features.
Once version 1.0 is release and SQUAD moves to this version this file
should be removed.
"""
import re
from collections import namedtuple
from urllib.parse import unquote

from django.db.models import QuerySet
from django.http import QueryDict
from django_filters.rest_framework import backends
from django.utils.translation import ugettext as _
from rest_framework.serializers import ValidationError as SerializerValidationError

from rest_framework_filters.filterset import FilterSet
from rest_framework.exceptions import ValidationError


# originally based on: https://regex101.com/r/5rPycz/1
# current iteration: https://regex101.com/r/5rPycz/3
# special thanks to @JohnDoe2 on the #regex IRC channel!
# matches groups of "<negate>(<encoded querystring>)<set op>"
COMPLEX_OP_RE = re.compile(r'()\(([^)]+)\)([^(]*?(?=\())?')
COMPLEX_OP_NEG_RE = re.compile(r'(~?)\(([^)]+)\)([^(]*?(?=~\(|\())?')
COMPLEX_OPERATORS = {
    '&': QuerySet.__and__,
    '|': QuerySet.__or__,
}

ComplexOp = namedtuple('ComplexOp', ['querystring', 'negate', 'op'])


def lookahead(iterable):
    it = iter(iterable)
    try:
        current = next(it)
    except StopIteration:
        return

    for value in it:
        yield current, True
        current = value
    yield current, False


def decode_complex_ops(encoded_querystring, operators=None, negation=True):
    """
    Returns a list of (querystring, negate, op) tuples that represent complex operations.
    This function will raise a `ValidationError`s if:
    - the individual querystrings are not wrapped in parentheses
    - the set operators do not match the provided `operators`
    - there is trailing content after the ending querysting
    Ex::
        # unencoded query: (a=1) & (b=2) | ~(c=3)
        >>> s = '%28a%253D1%29%20%26%20%28b%253D2%29%20%7C%20%7E%28c%253D3%29'
        >>> decode_querystring_ops(s)
        [
            ('a=1', False, QuerySet.__and__),
            ('b=2', False, QuerySet.__or__),
            ('c=3', True, None),
        ]
    """
    complex_op_re = COMPLEX_OP_NEG_RE if negation else COMPLEX_OP_RE
    if operators is None:
        operators = COMPLEX_OPERATORS

    # decode into: (a%3D1) & (b%3D2) | ~(c%3D3)
    decoded_querystring = unquote(encoded_querystring)
    matches = [m for m in complex_op_re.finditer(decoded_querystring)]

    if not matches:
        msg = _("Unable to parse querystring. Decoded: '%(decoded)s'.")
        raise SerializerValidationError(msg % {'decoded': decoded_querystring})

    results, errors = [], []
    for match, has_next in lookahead(matches):
        negate, querystring, op = match.groups()

        negate = negate == '~'
        querystring = unquote(querystring)
        op_func = operators.get(op.strip()) if op else None
        if op_func is None and has_next:
            msg = _("Invalid querystring operator. Matched: '%(op)s'.")
            errors.append(msg % {'op': op})

        results.append(ComplexOp(querystring, negate, op_func))

    trailing_chars = decoded_querystring[matches[-1].end():]
    if trailing_chars:
        msg = _("Ending querystring must not have trailing characters. Matched: '%(chars)s'.")
        errors.append(msg % {'chars': trailing_chars})

    if errors:
        raise SerializerValidationError(errors)

    return results


def combine_complex_queryset(querysets, complex_ops, negation=True):
    # Negate querysets
    for queryset, op in zip(querysets, complex_ops):
        if negation and op.negate:
            queryset.query.where.negate()

    # Combine querysets
    combined = querysets[0]
    for queryset, op in zip(querysets[1:], complex_ops[:-1]):
        combined = op.op(combined, queryset)

    return combined


class RestFrameworkFilterBackend(backends.DjangoFilterBackend):
    filterset_base = FilterSet

    def to_html(self, request, queryset, view):
        return super().to_html(request, queryset, view)


class ComplexFilterBackend(RestFrameworkFilterBackend):
    complex_filter_param = 'filters'
    operators = None
    negation = True

    def filter_queryset(self, request, queryset, view):
        if self.complex_filter_param not in request.query_params:
            return super().filter_queryset(request, queryset, view)

        # Decode the set of complex operations
        encoded_querystring = request.query_params[self.complex_filter_param]
        try:
            complex_ops = decode_complex_ops(encoded_querystring, self.operators, self.negation)
        except ValidationError as exc:
            raise ValidationError({self.complex_filter_param: exc.detail})

        # Collect the individual filtered querysets
        querystrings = [op.querystring for op in complex_ops]
        try:
            querysets = self.get_filtered_querysets(querystrings, request, queryset, view)
        except ValidationError as exc:
            raise ValidationError({self.complex_filter_param: exc.detail})

        return combine_complex_queryset(querysets, complex_ops)

    def get_filtered_querysets(self, querystrings, request, queryset, view):
        original_GET = request._request.GET

        querysets, errors = [], {}
        for qs in querystrings:
            request._request.GET = QueryDict(qs)
            try:
                result = super().filter_queryset(request, queryset, view)
                querysets.append(result)
            except ValidationError as exc:
                errors[qs] = exc.detail
            finally:
                request._request.GET = original_GET

        if errors:
            raise ValidationError(errors)
        return querysets
