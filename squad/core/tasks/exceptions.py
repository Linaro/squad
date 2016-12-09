import sys


class InvalidMetadataJSON(Exception):
    pass


class InvalidMetadata(Exception):
    pass


class InvalidMetricsDataJSON(Exception):
    pass


class InvalidTestsDataJSON(Exception):
    pass


m = sys.modules[__name__]
invalid_input = tuple((getattr(m, cls) for cls in dir(m) if cls.startswith('Invalid')))
