from django.db import models
from django.forms import MultipleChoiceField, ChoiceField, CheckboxSelectMultiple
from pkg_resources import EntryPoint, iter_entry_points
from pkgutil import iter_modules
import os


import squad


class PluginNotFound(Exception):
    pass


class PluginLoader(object):

    __plugins__ = None

    @classmethod
    def load_all(cls):
        if cls.__plugins__ is not None:
            return cls.__plugins__

        entry_points = []

        # builtin plugins
        builtin_plugins_path = os.path.join(squad.__path__[0], 'plugins')
        for _, m, _ in iter_modules([builtin_plugins_path]):
            e = EntryPoint(m, 'squad.plugins.' + m, attrs=('Plugin',))
            entry_points.append(e)

        # external plugins
        plugins = iter_entry_points('squad_plugins')
        entry_points += list(plugins)

        cls.__plugins__ = {e.name: e.resolve() for e in entry_points}
        return cls.__plugins__


def get_plugin_instance(name):
    try:
        plugin_class = PluginLoader.load_all()[name]
    except KeyError:
        raise PluginNotFound(name)
    return plugin_class()


def get_all_plugins():
    plugins = PluginLoader.load_all()
    return plugins.keys()


def get_plugins_by_feature(features):
    """
    Returns a list of plugin names where the plugins implement at least one of
    the *features*. *features* must a list of Plugin methods, e.g.
    [Plugin.postprocess_testrun, Plugin.postprocess_testjob]
    """
    if not features:
        return get_all_plugins()
    plugins = PluginLoader.load_all().items()
    names = set([f.__name__ for f in features])
    return [e for e, plugin in plugins if names & set(plugin.__dict__.keys())]


def apply_plugins(plugin_names):
    """
    This function should be used by code in the SQUAD core to trigger
    functionality from plugins.

    The ``plugin_names`` argument is list of plugins names to be used. Most
    probably, you will want to pass the list of plugins enabled for a given
    project, e.g.  ``project.enabled_plugins``.

    Example::

        from squad.core.plugins import apply_plugins

        # ...

        for plugin in apply_plugins(project.enabled_plugins):
            plugin.method(...)

    """
    if plugin_names is None:
        return

    for p in plugin_names:
        try:
            plugin = get_plugin_instance(p)
            yield plugin
        except PluginNotFound:
            pass


class Plugin(object):
    """
    This class must be used as a superclass for all SQUAD plugins. All the
    methods declared here have empty implementations (i.e. they do nothing),
    and should be overriden in your plugin to provide extra functionality to
    the SQUAD core.
    """

    def postprocess_testrun(self, testrun):
        """
        This method is called after a test run has been received by SQUAD, and
        the test run data (tests, metrics, metadata, logs, etc) have been saved
        to the database.

        You can use this method to parse logs, do any special handling of
        metadata, test results, etc.

        The ``testrun`` arguments is an instance of
        ``squad.core.models.TestRun``.
        """
        pass

    def postprocess_testjob(self, testjob):
        """
        This method is called after a test job has been fetched by SQUAD, and
        the test run data (tests, metrics, metadata, logs, etc) have been saved
        to the database.

        You can use this method to do any processing that is specific to a
        given CI backend (e.g. LAVA).

        The ``testjob`` arguments is an instance of
        ``squad.ci.models.TestJob``.
        """
        pass

    def notify_patch_build_created(self, build):
        """
        This method is called when a patch build is created. It should notify
        the corresponding patch source that the checks are in progress.

        The ``build`` argument is an instance of ``squad.core.Build``.
        """
        pass

    def notify_patch_build_finished(self, build):
        """
        This method is called when a patch build is finished. It should notify
        the patch source about the status of the tests (success, failure, etc).

        The ``build`` argument is an instance of ``squad.core.Build``.
        """
        pass

    def get_url(self, object_id):
        """
        This method might return service specific URL with given object_id
        """
        pass


class PluginField(models.CharField):

    def __init__(self, **args):
        defaults = {'max_length': 256}
        defaults.update(args)
        self.features = defaults.pop('features', None)
        return super(PluginField, self).__init__(**defaults)

    def deconstruct(self):
        name, path, args, kwargs = super(PluginField, self).deconstruct()
        del kwargs["max_length"]
        return name, path, args, kwargs

    def formfield(self, **kwargs):
        plugins = ((v, v) for v in get_plugins_by_feature(self.features))
        return ChoiceField(choices=plugins)


class PluginListField(models.TextField):

    def __init__(self, **args):
        self.features = args.pop('features', None)
        return super(PluginListField, self).__init__(**args)

    def from_db_value(self, value, *args):
        if value is None:
            return None
        return [item.strip() for item in value.split(',')]

    def to_python(self, value):
        if isinstance(value, list):
            return value
        if value is None:
            return None
        return [item.strip() for item in value.split(',')]

    def get_prep_value(self, value):
        if value is None:
            return value
        return ', '.join(value)

    def formfield(self, **kwargs):
        plugins = ((v, v) for v in get_plugins_by_feature(self.features))
        required = not self.null
        return MultipleChoiceField(
            required=required,
            choices=plugins,
            widget=CheckboxSelectMultiple,
        )
