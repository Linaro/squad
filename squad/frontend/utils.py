import mimetypes


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
