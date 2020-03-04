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

SQUAD plugins are Python classes that are a subclass of `squad.core.plugins.Plugin`,
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

    from squad.core.plugins import Plugin

    class Plugin1(Plugin):
        # implementation of the plugin methods ...

    class Plugin2(Plugin):
        # implementation of the plugin methods ...

The next next section, "The plugin API" documents which methods can be defined
in your plugin class in order to provide extra functionality to the SQUAD core.

The plugin API
--------------

.. autoclass:: squad.core.plugins.Plugin
    :members:

Adding plugin usage to the SQUAD core
-------------------------------------

Code from the SQUAD core that wants to invoke functionality from plugins should
use the ``apply_plugins`` function.

.. autofunction:: squad.core.plugins.apply_plugins

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

    from squad.core.plugins import Plugin

    class MyPlugin(Plugin):

        def postprocess_testrun(self, testrun):
        # do something interesting with the the testrun ...
            pass

Built-in notification plugins
-----------------------------

SQUAD comes with two bult-in plugins available for immediate use.

Github
~~~~~~

The Github plugin allows patches (Pull Requests) originated from Github
to be notified whenever a build has been created or finished.

Here is an example API call that supposedly came from a Jenkins job, triggered
by a freshly opened Github Pull Request::

    $ curl \
        -X POST \
        --header "Auth-Token: $SQUAD_TOKEN" \
        --patch_source=your-github-patch-source \
        --patch_baseline=build-v1 \
        --patch_id=the_owner/the_repo/8223a534d7bf \
        https://squad.example.com/api/createbuild/my-group/my-project/build-v2

Where:
 - `patch_source` is the name of a "Patch Source" previously added in squad
   in "Administration > Core > Patch sources > Add patch source", where you should
   select "github" for "implementation". **NOTE** the Github plugin requires a 
   `token` for authentication, so please ignore the "password" field.
 - `patch_baseline` is an optional parameter that indicated that the build being
   created is a new version of "patch_baseline" build.
 - `patch_id` is a string in a form like "owner/repository/commit" of the respective
   Github repository.

If everything was successfully submitted, you should see a notification in the Github
page for that Pull Request. Subsequent tests on that build are going to be performed
and as SQUAD detects that all tests are done, another notification should be sent out
on that Pull Request, informing that the build is finished.

Gerrit
~~~~~~

The Gerrit plugin allows changes originated from a Gerrit instance
to be notified whenever a build has been created or finished.

Here is an example API call that supposedly came from a Jenkins job, triggered
by a freshly created change::

    $ curl \
        -X POST \
        --header "Auth-Token: $SQUAD_TOKEN" \
        --patch_source=your-gerrit-patch-source \
        --patch_baseline=build-v1 \
        --patch_id=change-id/patchset \
        https://squad.example.com/api/createbuild/my-group/my-project/build-v2

Where:
 - `patch_source` is the name of a "Patch Source" previously added in squad
   in "Administration > Core > Patch sources > Add patch source", where you should
   select "gerrit" for "implementation". **NOTE 1** the Gerrit plugin requires a 
   `password` (configured as HTTP Password in Gerrit) for authentication, so please
   ignore the "token" field. **NOTE 2** the Gerrit plugin also allows SSH based
   notifications by using "ssh://" instead of "https://" in the "url" field.
   **NOTE 3** SSH connections are made only through key exchange, so please set it
   up before attempting to use this feature
 - `patch_baseline` is an optional parameter that indicated that the build being
   created is a new version of "patch_baseline" build.
 - `patch_id` is a string in a form like "change-id/patchset" of the respective Gerrit
   repository.

If everything was successfully submitted, you should see a notification in the Gerrit
page for that Change. Subsequent tests on that build are going to be performed
and as SQUAD detects that all tests are done, another notification should be sent out
on that Change, informing that the build is finished.

.. vim: ts=4 sw=4 et=1
