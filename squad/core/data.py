import json
from statistics import mean


class JSONTestDataParser(object):
    """
    Parser for test data as JSON string
    """

    @staticmethod
    def __call__(test_data):
        if test_data is None or test_data == '':
            return []

        input_data = json.loads(test_data)
        data = []
        for key, value in input_data.items():
            group_name, test_name = parse_name(key)
            data.append({
                "group_name": group_name,
                "test_name": test_name,
                "pass": value == 'pass',
            })
        return data


def parse_name(input_name):
    group_name = None
    name = input_name

    parts = input_name.split('/')
    if len(parts) > 1:
        group_name = '/'.join(parts[0:-1])
        name = parts[-1]

    return (group_name, name)


def parse_metric(value):
    if isinstance(value, list):
        return mean(value), value
    else:
        return value, [value]


class JSONMetricDataParser(object):
    """
    Parser for JSON metric data
    """

    @staticmethod
    def __call__(json_text):
        if json_text is None or json_text == '':
            return []

        input_data = json.loads(json_text)
        data = []

        for key, value in input_data.items():
            group_name, name = parse_name(key)
            result, measurements = parse_metric(value)
            data.append({
                "name": name,
                "group_name": group_name,
                "result": result,
                "measurements": measurements,
            })

        return data
