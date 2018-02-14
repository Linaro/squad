import random
import string
from django.template.defaultfilters import safe, escape


def random_key(length, chars=string.printable):
    return ''.join(random.SystemRandom().choice(chars) for _ in range(length))


def random_token(length):
    chars = string.ascii_letters + string.digits
    return random_key(length, chars=chars)


def parse_name(input_name):
    group_name = None
    name = input_name

    parts = input_name.split('/')
    if len(parts) > 1:
        # if test name is in format suite/complex.name[some/test/variant]
        # don't split the name in brackets
        # this is workaround for some CTS test names
        if parts[-1].endswith("]"):
            index = len(parts) - 1
            # find index of the part that contains opening bracket
            for part in reversed(parts):
                if "[" in part:
                    index = parts.index(part)
            group_name = '/'.join(parts[0:index])
            name = '/'.join(parts[index:])
        else:
            group_name = '/'.join(parts[0:-1])
            name = parts[-1]

    if group_name == '' or group_name is None:
        group_name = '/'

    return (group_name, name)


def join_name(group, name):
    if group == '/':
        return name
    else:
        return "/".join([group, name])


def format_metadata(v, separator):
    if type(v) is list:
        return safe(separator.join([escape(t) for t in v]))
    else:
        return escape(v)
