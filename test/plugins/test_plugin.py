from django.test import TestCase
from squad.core.plugins import get_plugin_instance, get_plugins_by_feature, apply_plugins
from squad.core.plugins import Plugin, PluginNotFound


class TestGetPluginsByFeature(TestCase):

    def test_basics(self):
        testrun_plugins = get_plugins_by_feature([Plugin.postprocess_testrun])
        testjob_plugins = get_plugins_by_feature([Plugin.postprocess_testjob])
        self.assertNotIn('example', testrun_plugins)
        self.assertNotIn('linux_log_parser', testjob_plugins)
        self.assertIn('linux_log_parser', testrun_plugins)

    def test_feature_list_is_none(self):
        plugins = get_plugins_by_feature(None)
        self.assertIn('example', plugins)
        self.assertIn('linux_log_parser', plugins)

    def test_empty_feature_list(self):
        plugins = get_plugins_by_feature([])
        self.assertIn('example', plugins)
        self.assertIn('linux_log_parser', plugins)


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
