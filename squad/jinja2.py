from importlib import import_module
from jinja2 import Environment, select_autoescape
from django.contrib.staticfiles.storage import staticfiles_storage
from django.utils import translation


import inspect


# it'd be better to have a generic auto loader
# but we only have a few templatetags for now...
_templatetags_modules = [
    'squad.frontend.templatetags.squad',
    'squad.ci.templatetags.filter_jobs',
    'squad.core.templatetags.squad_notification',
]

_django_default_filter_modules = [
    'django.template.defaultfilters',
    'django.contrib.humanize.templatetags.humanize',
]

_local_env = {
    'globals': {
        'static': staticfiles_storage.url,
    },
    'filters': {},
    'tests': {}
}


def environment(**options):
    _load_django_default_filters()
    _load_templatetags()

    env = Environment(**options)
    env.globals.update(_local_env['globals'])
    env.filters.update(_local_env['filters'])
    env.tests.update(_local_env['tests'])
    env.install_gettext_translations(translation)
    env.autoescape = select_autoescape(
        disabled_extensions=('txt.jinja2',),
        default_for_string=False,
        default=True)
    return env


def register_global_function(*args, **kwargs):
    return _register('globals', *args, **kwargs)


def register_test(*args, **kwargs):
    return _register('tests', *args, **kwargs)


def register_filter(*args, **kwargs):
    return _register('filters', *args, **kwargs)


def _register(attr, fn=None, name=None, takes_context=None):
    # needs to be a function that receives func being decorated
    if fn is None:
        def dec(func):
            return _update_local_env(attr, func, name, takes_context)
    else:
        return _update_local_env(attr, fn, name, takes_context)

    return dec


def _update_local_env(attr, func, name=None, takes_context=None):
    global _local_env

    if takes_context:
        func.contextfunction = True

    if name is None:
        name = func.__name__

    _local_env[attr][name] = func

    return func


def _load_templatetags():
    for mod in _templatetags_modules:
        try:
            import_module(mod)
        except ImportError:
            pass


def _load_django_default_filters():
    for s_mod in _django_default_filter_modules:
        mod = import_module(s_mod)

        all_funcs = inspect.getmembers(mod, inspect.isfunction)

        for tupl in all_funcs:
            name, func = tupl

            if name[0] != '_' and func.__module__ == mod.__name__:
                register_filter(func)
