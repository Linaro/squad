.. _production_install_ref_label:

=====================================================
Installation Instructions for production environments
=====================================================

Installation using the Python package manager pip
-------------------------------------------------

Make sure you have the ``pip`` Python package manager installed on your Python 3
environment, and the C library for YAML development. On Debian/Ubuntu,
the easiest way to do that is::

    apt-get install python3-pip libyaml-dev libpq-dev

Install squad::

    pip3 install squad

Message broker
--------------

In order to SQUAD processes to be able to communicate between each other, you
need to install an AMQP server. We recommend RabbitMQ::

    apt-get install rabbitmq-server

By default SQUAD will look for an AMQP server running on localhost, listening
to the standard port, so for a single-server deployment you don't need to do
anything else.

If you have a multi-server setup, then each server needs to be configured with
the location of a central AMQP server. See the `SQUAD_CELERY_BROKER_URL` in the
"Further configuration" section below.

Processes
---------

SQUAD is composed of 4 different process:

* web application server
* background worker (celery worker)
* periodic task scheduler (celery beat)
* CI backend listener

To run the web interface, run as a dedicated user (i.e. don't run the
application as ``root``!)::

    squad

* Note: if that doesn't work, ``~/.local/bin`` is probably missing in the ``$PATH`` environment variable.

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

These are the command lines to run the other processes:

+-----------+---------------------------+
| Process   | Command                   |
+===========+===========================+
| worker    | celery -A squad worker    |
+-----------+---------------------------+
| scheduler | celery -A squad beat      |
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

Worker configuration
--------------------

The `worker` process handles background tasks, such as submitting CI jobs,
fetching the results fo CI jobs, preparing reports that require intensive
processing, etc. Some tasks take a lot longer than the others, e.g. submitting
a CI job is pretty quick, while fetching CI job results takes some time to
fetch all the data, parse it, and store in the database.

To allow for better load balancing, these tasks are split into multiple queues:

* `ci_fetch`
* `ci_poll`
* `ci_quick`
* `core_notification`
* `core_postprocess`
* `core_quick`
* `core_reporting`

`ci_fetch` and `ci_poll` can be potentially slow, and if there is a large
influx of those types of tasks, your system may display some congestion because
all available worker threads are occupied running slow tasks, while several of
the quick ones are waiting their turn.

To avoid this, you might want to start a small part of your workers so that
they will not pick up any of those slow tasks::

    squad worker --exclude-queues ci_fetch,ci_poll

Or you can also give an explicit task list, which is less flexible but might be
useful::

    squad worker --queues core_quick,ci_quick

By default, workers listen to all queues.

For message brokers that support prefixed-queue names, SQUAD has the optional
environment variable `SQUAD_CELERY_QUEUE_NAME_PREFIX`, that, if set, will
prepend it before all queue names. SQUAD also support adding a suffix via
the optional environment variable `SQUAD_CELERY_QUEUE_NAME_SUFFIX`

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

* ``SQUAD_EMAIL_HOST``: hostname to use as e-mail delivery host. Sets Django's
  ``EMAIL_HOST`` setting. See the `Django documentation on sending email`__ for
  more details.

__ https://docs.djangoproject.com/en/1.11/topics/email/

* ``SQUAD_LOGIN_MESSAGE``: a message to be displayed to users right above the
  login form. Use for example to provide instructions on what credentials to
  use. Defaults no message.

* ``SQUAD_ADMINS``: Comma-separated list of administrator email addresses, for
  use in exception notifications. Each address must be formatted as
  ``First Last <first.last@example.com>``.

* ``SQUAD_STATIC_DIR``: Directory where SQUAD will find it's preprocessed
  static assets. This usually does not need to be set manually, and exists
  mostly for use in the Docker image.

* ``SQUAD_CELERY_BROKER_URL``: URL to the broker to be used by Celery for
  background jobs. Defaults to ``amqp://localhost:5672``.

* ``SQUAD_CELERY_QUEUE_NAME_PREFIX``: Name to prefix all queues in Celery.
  Useful when multiple environments share the same broker.
  Defaults to ``''``.

* ``SQUAD_CELERY_QUEUE_NAME_SUFFIX``: Name to concatenate all queues in Celery.
  Useful when a queue extension is needed by the broker.
  Defaults to ``''``.

* ``SQUAD_CELERY_POLL_INTERVAL``: Number of seconds a worker will sleep
  after an empty answer from SQS before the next polling attempt.
  Defaults to ``1``.

User management
---------------

SQUAD provides 'users' management command that allows to list, add, update
and display details about users. This command comes handy when trying to
automate SQUAD setup with containers. Details about user management with
'users' command:

 * list
   Displays list of all available users with their names (first, last)
   from database

 * details <username>
   Displays details about requested username. Details include:

   * username
   * is_active
   * is_staff
   * is_superuser
   * groups

 * add <username>
   Adds new user with given 'username'. It also takes additional parameters

   * --email EMAIL email of the user
   * --passwd PASSWD Password for this user. If empty, a random password is
     generated.
   * --staff Make this user a staff member
   * --superuser Make this user a super user

 * update <username>
   Updates database record of existing user identified with 'username'. It takes
   additional parameters

   * --email EMAIL Change email of the user
   * --active Make this user active
   * --not-active Make this user inactive
   * --staff Make this user a staff member
   * --not-staff Make this user no longer a staff member
   * --superuser Make this user a superuser
   * --not-superuser Make this user no longer a superuser
