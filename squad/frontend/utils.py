import mimetypes
import re


file_mapping = (
    ('text/x-', 'code'),
    ('text/', 'text'),
    ('application/pdf', 'text'),
    ('image/', 'image'),
    ('audio/', 'audio'),
    ('video/', 'video'),
    ('application/gzip', 'archive'),
    ('application/z-xz', 'archive'),
    ('application/zip', 'archive'),
    ('application/x-', 'code'),
)


def file_type(filename):
    content_type, _ = mimetypes.guess_type(filename)

    if content_type is None:
        return None

    for pattern, ftype in file_mapping:
        if pattern in content_type:
            return ftype

    return None


regex_numbers = re.compile('([0-9]+)')


def _alphanum_key(field):
    def _key(o):
        parts = regex_numbers.split(str(getattr(o, field)))
        return [int(part) if part.isdigit() else part for part in parts]
    return _key


def alphanum_sort(objects, field, reverse=True):
    """
    Django's `order_by` does not provide natural order, e.g.:
    project-name-v4.14 comes before project-name-v4.4
    The alphanumeric_sort forces natural sorting, so that the
    example above, v4.4 would come before v4.14
    ref: https://blog.codinghorror.com/sorting-for-humans-natural-sort-order
    """
    return sorted(list(objects), reverse=reverse, key=_alphanum_key(field))
