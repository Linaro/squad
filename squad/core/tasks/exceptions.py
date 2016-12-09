import sys


class InvalidMetadataJSON(Exception):
    pass


class InvalidMetadata(Exception):
    pass


class InvalidMetricsDataJSON(Exception):
    pass


class InvalidMetricsData(Exception):

    @classmethod
    def type(cls, obj):
        return cls("%r is not an object ({})" % obj)

    @classmethod
    def value(cls, value):
        return cls("metric value %r is not valid. only numbers or lists of numbers are accepted" % value)


class InvalidTestsDataJSON(Exception):
    pass


m = sys.modules[__name__]
invalid_input = tuple((getattr(m, cls) for cls in dir(m) if cls.startswith('Invalid')))
