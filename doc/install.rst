=====================================================
Installation Instructions for production environments
=====================================================

Installation using the Python package manager pip
-------------------------------------------------

Make sure you have the ``pip`` Python package manager installed on your Python 3
environment. On Debian/Ubuntu, the easiest way to do that is::

    apt-get install python3-pip

Install squad::

    pip3 install squad


Processes
---------

SQUAD is composed of 4 different process:

* web application server
* background worker (celery worker)
* periodic task scheduler (celery beat)
* CI backend listener

The only mandatory process if the web interface. The others are optional and
are only needed if you need features like email notification and CI loop
integration.

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

These are the command lines to run the other processes, for the CI loop
integration:

+-----------+----------------------------
| Process   | Command                   |
+-----------+---------------------------+
| worker    | squad-admin celery worker |
+-----------+---------------------------+
| scheduler | squad-admin celery beat   |
+-----------+---------------------------+
| listener  | squad-admin listen        |
+-----------+---------------------------+

You most probably want all the processes (including the web interface) being
managed by a system manager such as systemd__, or a process manager such as
supervisor__.

__ https://www.freedesktop.org/wiki/Software/systemd/
__ http://supervisord.org/

For an example deployment, check the configuration management repository for
`Linaro's qa-reports`__ (using ansible).

__ https://github.com/Linaro/qa-reports.linaro.org

After having the necessary processes running, there are a few extra setup steps
needed:

* Create ``Backend`` instances for your test execution backends. Go to the
  administration web UI, and under "CI", choose "Backends".
* For each project, create authentication tokens and subscriptions
* Under "Djcelery", create "Periodic tasks":

  * ``squad.ci.tasks.poll``: this is that task to  poll results from the
    backends from time to time. You can schedule this for every 5 minutes;

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

* ``DJANGO_LOG_LEVEL``: the logging level used for Django-related logging.
  Default: ``INFO``.

* ``SQUAD_LOG_LEVEL``: the logging level for SQUAD-specific logging. Default:
  ``INFO``.

* ``SQUAD_HOSTNAME``: hostname used to compose links in asynchronous
  notifications (e.g. emails). Defaults to the FQDN of the host where SQUAD is
  running.

* ``SQUAD_BASE_URL``: Base URL to the SQUAD web interface, used when composing
  links in notifications (e.g. emails). Defaults to
  ``https://$SQUAD_HOSTNAME``.

* ``SQUAD_EMAIL_FROM``: e-mail used as sender of email notifications. Defaults
  to ``noreply@$SQUAD_HOSTNAME``.

* ``SQUAD_LOGIN_MESSAGE``: a message to be displayed to users right above the
  login form. Use for example to provide instructions on what credentials to
  use. Defaults no message.

* ``SQUAD_ADMINS``: Comma-separated list of administrator email addresses, for
  use in exception notifications. Each address must be formatted as
  ``First Last <first.last@example.com>``.

* ``SQUAD_STATIC_DIR``: Directory where SQUAD will find it's preprocessed
  static assets. This usually does not need to be set manually, and exists
  mostly for use in the Docker image.

