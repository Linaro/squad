from django.test import TestCase
from squad.plugins import get_plugin_instance, apply_plugins
from squad.plugins import Plugin, PluginNotFound


class TestGetPuginInstance(TestCase):

    def test_example(self):
        plugin = get_plugin_instance('example')
        self.assertIsInstance(plugin, Plugin)

    def test_nonexisting(self):
        with self.assertRaises(PluginNotFound):
            get_plugin_instance('nonexisting')


class TestApplyPlugins(TestCase):

    def test_skips_nonexisting_plugins(self):
        plugins = []
        for plugin in apply_plugins(['example', 'nonexisting']):
            plugins.append(plugin)
        self.assertEqual(1, len(plugins))
        self.assertIsInstance(plugins[0], Plugin)
