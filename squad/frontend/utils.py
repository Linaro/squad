import mimetypes


file_mapping = {
    'code': (
        'text/x-'
    ),
    'text': (
        'text/',
        'application/pdf',
    ),
    'image': (
        'image/',
    ),
    'audio': (
        'audio/',
    ),
    'video': (
        'video/',
    ),
    'archive': (
        'application/gzip',
        'application/z-xz',
        'application/zip',
    ),
}


def file_type(filename):
    content_type, _ = mimetypes.guess_type(filename)

    if content_type is None:
        return None

    for candidate, patterns in file_mapping.items():
        for p in patterns:
            if p in content_type:
                return candidate

    return None
