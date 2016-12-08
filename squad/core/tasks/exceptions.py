class InvalidMetadataJSON(Exception):
    pass


class InvalidMetricsDataJSON(Exception):
    pass


class InvalidTestsDataJSON(Exception):
    pass


invalid_input = (
    InvalidMetadataJSON,
    InvalidMetricsDataJSON,
    InvalidTestsDataJSON,
)
