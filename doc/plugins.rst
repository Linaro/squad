==============================
Plugins: usage and development
==============================

Enabling plugins
----------------

Every available plugin needs to be enabled for each project in which it should
be used. For that, access the Administration interface, edit the project, and
add the wanted plugin names to the "Enabled plugin list" field.

Declaring plugins in your Python package
----------------------------------------

SQUAD plugins are Python classes that are a subclass of `squad.plugins.Plugin`,
and can be provided by any Python package installed in the system. To register
the plugin with SQUAD, you need to use the "entry points" system. In the
setup.py for your package, use the following::

    setup(
        # ...
        packages='mypluginpackage'
        # ...
        entry_points={
            # ...
            'squad_plugins': [
                'myplugin1=mypluginpackage.Plugin1',
                'myplugin2=mypluginpackage.Plugin2',
            ]
        },
        # ...
    )

Now, the plugin itself can be implemented in `mypluginpackage.py`, like this::

    from squad.plugins import Plugin

    class Plugin1(Plugin):
        # implementation of the plugin methods ...

    class Plugin2(Plugin):
        # implementation of the plugin methods ...

The next next section, "The plugin API" documents which methods can be defined
in your plugin class in order to provide extra functionality to the SQUAD core.

The plugin API
--------------

.. autoclass:: squad.plugins.Plugin
    :members:

Adding plugin usage to the SQUAD core
-------------------------------------

Code from the SQUAD core that wants to invoke functionality from plugins should
use the ``apply_plugins`` function.

.. autofunction:: squad.plugins.apply_plugins

Full plugin package example
---------------------------

This section presents a minimal, working example of a Python package that
provides one SQUAD plugin. It is made of only two files: ``setup.py`` and
``examplepluginpackage/__init__.py``.

``setup.py``::

    from setuptools import setup, find_packages

    setup(
        name='examplepluginpackage',
        version='1.0',
        author='Plugin Writer',
        author_email='plugin.writer@example.com',
        url='https://example.com/examplepluginpackage',
        packages=find_packages(),
        include_package_data=True,
        entry_points={
            'squad_plugins': [
                'externalplugin=examplepluginpackage:MyPlugin',
            ]
        },
        license='AGPLv3+',
        description="An example Plugin pacakge",
        long_description="""
        The Example Plugin package is a sample plugin for SQUAD that
        shows how to write SQUAD plugins
        """,
        platforms='any',
    )


``examplepluginpackage/__init__.py``::

    from squad.plugins import Plugin

    class MyPlugin(Plugin):

        def postprocess_testrun(self, testrun):
        # do something interesting with the the testrun ...
            pass


.. vim: ts=4 sw=4 et=1
