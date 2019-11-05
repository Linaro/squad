import random
import string
import yaml
import jinja2


from django.template.defaultfilters import safe, escape
from django.core.exceptions import ValidationError
from django.conf import settings


def random_key(length, chars=string.printable):
    return ''.join(random.SystemRandom().choice(chars) for _ in range(length))


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


def yaml_validator(value):
    if value is None:
        return
    if len(value) == 0:
        return
    try:
        if not isinstance(yaml.safe_load(value), dict):
            raise ValidationError("Dictionary object expected")
    except yaml.YAMLError as e:
        raise ValidationError(e)


def jinja2_validator(template):
    if template is None or len(template) == 0:
        return
    try:
        env = jinja2.Environment()
        if not isinstance(env.parse(template), jinja2.nodes.Template):
            raise ValidationError("Jinja2 template object expected")
    except jinja2.exceptions.TemplateSyntaxError as e:
        raise ValidationError(e)


def repeat_to_length(s, wanted):
    return (s * ((wanted // len(s)) + 1))[:wanted]


# xor cipher: https://en.wikipedia.org/wiki/XOR_cipher
def xor(s, t):
    if isinstance(s, str):
        return ''.join([chr(ord(a) ^ ord(b)) for a, b in zip(s, t)])
    else:
        return bytes([a ^ b for a, b in zip(s, t)])


def encrypt(text):
    key = repeat_to_length(settings.SECRET_KEY, len(text))
    return xor(text, key)


def decrypt(crypted):
    key = repeat_to_length(settings.SECRET_KEY, len(crypted))
    return xor(crypted, key)


def split_dict(_dict, chunk_size=1):
    dict_size = len(_dict)

    if dict_size <= chunk_size:
        return [_dict]

    chunks = []
    chunk = {}
    counter = 0
    keys = list(_dict.keys())

    for key in keys:
        chunk[key] = _dict.pop(key)
        counter += 1
        if counter == chunk_size:
            chunks.append(chunk)
            counter = 0
            chunk = {}

    if len(chunk):
        chunks.append(chunk)

    return chunks


def split_list(_list, chunk_size=1):
    chunks = []
    while _list:
        chunks.append(_list[:chunk_size])
        _list = _list[chunk_size:]
    return chunks
