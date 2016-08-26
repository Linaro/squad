import json


class JSONTestDataParser(object):
    """
    Parser for test data as JSON string
    """

    @staticmethod
    def __call__(test_data):
        input_data = json.loads(test_data)
        data = []
        for key, value in input_data.items():
            group_name = None
            test_name = key

            parts = key.split('/')
            # TODO: more than 2 parts (i.e. more than one /) is not valid
            if len(parts) == 2:
                group_name = parts[0]
                test_name = parts[1]

            data.append({
                "group_name": group_name,
                "test_name": test_name,
                "pass": value == 'pass',
            })
        return data
