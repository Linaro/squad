import random
import string
import yaml
import jinja2
import hashlib
import base64


from cryptography.fernet import Fernet


from django.template.defaultfilters import safe, escape
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils.encoding import force_str as force_text


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


def __get_cryptographic_key__():
    sha256_object = hashlib.sha256()
    sha256_object.update(str.encode(settings.SECRET_KEY))
    key = base64.b64encode(str.encode(sha256_object.hexdigest()[:32]))
    return key


def encrypt(clear_text):
    key = __get_cryptographic_key__()
    return Fernet(key).encrypt(str.encode(clear_text)).decode()


def decrypt(crypted_text):
    key = __get_cryptographic_key__()
    return Fernet(key).decrypt(str.encode(crypted_text)).decode()


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


def _log_entry(request, object, message, flag):
    from django.contrib.auth.models import AnonymousUser
    from django.contrib.contenttypes.models import ContentType
    from squad.http import auth_user_from_request
    user = request.user
    if isinstance(user, AnonymousUser):
        user = auth_user_from_request(request, request.user)
    if not isinstance(user, AnonymousUser):
        from django.contrib.admin.models import LogEntry
        LogEntry.objects.log_action(
            user_id=user.pk,
            content_type_id=ContentType.objects.get_for_model(object).pk,
            object_id=object.pk,
            object_repr=force_text(object),
            action_flag=flag,
            change_message=message,
        )


def log_addition(request, object, message):
    from django.contrib.admin.models import ADDITION
    _log_entry(request, object, message, ADDITION)


def log_change(request, object, message):
    from django.contrib.admin.models import CHANGE
    _log_entry(request, object, message, CHANGE)


def log_deletion(request, object, message):
    from django.contrib.admin.models import DELETION
    _log_entry(request, object, message, DELETION)


def storage_save(obj, storage_field, filename, content):
    content_bytes = content or ''
    if type(content_bytes) == str:
        content_bytes = content_bytes.encode()
    filename = '%s/%s/%s' % (obj.__class__.__name__.lower(), obj.pk, filename)
    storage_field.save(filename, ContentFile(content_bytes))
