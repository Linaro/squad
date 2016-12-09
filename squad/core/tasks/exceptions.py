class InvalidMetadataJSON(Exception):
    pass


class InvalidMetadata(Exception):
    pass


class InvalidMetricsDataJSON(Exception):
    pass


class InvalidTestsDataJSON(Exception):
    pass


invalid_input = (
    InvalidMetadataJSON,
    InvalidMetadata,
    InvalidMetricsDataJSON,
    InvalidTestsDataJSON,
)
