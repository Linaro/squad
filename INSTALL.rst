SQUAD - Installation Instructions
=================================

Installation using the Python package manager pip
-------------------------------------------------

Make sure you have the ``pip`` Python package manager installed on your Python 3
environment. On Debian/Ubuntu, the easiest way to do that is::

    apt-get install python3-pip

Install squad::

    pip3 install squad


To run the web interface, run as a dedicated user (i.e. don't run the
application as ``root``!)::

    squad

This will make the web UI available at http://localhost:8000/. To serve the UI
to external users, you will need to setup a public-facing web server such as
Apache or nginx and reverse proxy to localhost on port 8000. You can change the
address or port SQUAD listens to by passing the ``--bind`` command line option,
e.g. to make it listen to port 5000 on the local loopback interface, use::

    squad --bind 127.0.0.0:5000

For production usage, you will want to tweak at least the database
configuration. Keep reading for more information.

After starting SQUAD, but before acessing it, you will need a user. To create
an admin user for yourself, use::

    squad-admin createsuperuser

Further configuration
---------------------

The following environment variables affect the behavior of SQUAD:

* ``DATABASE``: controls the database connection parameters. Should contain
  ``KEY=VALUE`` pairs, separated by colons (``:``).

  By default, SQUAD will use a SQLite3 database in its internal data directory.

  For example, to use a PostgreSQL database (requires the ``psycopg2`` Python
  package to be installed)::

      DATABASE=ENGINE=django.db.backends.postgresql_psycopg2:NAME=mydatabase:USER=myuser:HOST=myserver:PASSWORD=mypassword

* ``SQUAD_EXTRA_SETTINGS``: path to a Python file with extra Django settings.

* ``SQUAD_SITE_NAME``: name to be displayed at the page title and navigation
  bar. Defaults to 'SQUAD'.

* ``XDG_DATA_HOME``: parent directory of the SQUAD internal data directory.
  Defaults to ``~/.local/share``.  The actual data directory will be
  ``${XDG_DATA_HOME}/squad``.

* ``SECRET_KEY_FILE``: file to store encryption key for user sessions. Defaults
  to ``${XDG_DATA_HOME}/squad/secret.dat``
