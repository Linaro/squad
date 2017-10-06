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
    for p in plugin_names:
        try:
            plugin = get_plugin_instance(p)
            yield(plugin)
        except PluginNotFound:
            pass


class Plugin(object):

    def postprocess_testrun(self, testrun):
        pass
