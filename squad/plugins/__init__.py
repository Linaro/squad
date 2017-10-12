from pkg_resources import EntryPoint, iter_entry_points
from pkgutil import iter_modules


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
        for _, m, _ in iter_modules(['squad/plugins']):
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


def apply_plugins(plugin_names):
    """
    This function should be used by code in the SQUAD core to trigger
    functionality from plugins.

    The ``plugin_names`` argument is list of plugins names to be used. Most
    probably, you will want to pass the list of plugins enabled for a given
    project, e.g.  ``project.enabled_plugins``.

    Example::

        from squad.plugins import apply_plugins

        # ...

        for plugin in apply_plugins(project.enabled_plugins):
            plugin.method(...)

    """
    for p in plugin_names:
        try:
            plugin = get_plugin_instance(p)
            yield(plugin)
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
