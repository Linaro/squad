import sys


class DuplicatedTestJob(Exception):
    pass


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


class InvalidTestsData(Exception):
    @classmethod
    def type(cls, obj):
        return cls("%r is not an object ({})" % obj)

    @classmethod
    def value(cls, value):
        return cls("%r is not a valid test result. Only \"pass\" and \"fail\" are accepted" % value)


m = sys.modules[__name__]
invalid_input = tuple((getattr(m, cls) for cls in dir(m) if cls.startswith('Invalid')))
