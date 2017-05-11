SQUAD - Software Quality Dashboard
==================================

Quick start
-----------

SQUAD is a Django application and works just like any other Django
application. If you are new to Django and want to setup a development
environment, you can follow the instructions below. If you want to
install SQUAD for production usage, see [INSTALL](INSTALL.rst) instead.

Note that SQUAD is Python3-only, so it won't work with Python 2.

If running from git, you need to install a few packages needed for the
web frontend::

    apt-get install fonts-font-awesome libjs-angularjs libjs-bootstrap libjs-lodash

To install the dependencies::

    pip3 install -r requirements-dev.txt

Alternatively to using pip, on Debian stretch or later you can install
dependencies from the repository::

    apt-get install python3-dateutil python3-django python3-whitenoise

To run the tests::

    python3 manage.py test

Before running the application, create a admin user for yourself::

    python3 manage.py createsuperuser

To run the application locally::

    python3 manage.py runserver

Core data model
---------------

::

    +----+  * +-------+  * +-----+  * +-------+  * +----+ *   1 +-----+
    |Team|--->|Project|--->|Build|--->|TestRun|--->|Test|------>|Suite|
    +----+    +---+---+    +-----+    +-------+    +----+       +-----+
                  ^ *         ^         | *   |                    ^ 1
                  |           |         |     |  * +------+ *      |
              +---+--------+  |         |     +--->|Metric|--------+
              |Subscription|  |         |          +------+
              +------------+  |         v 1
              +-------------+ |       +-----------+
              |ProjectStatus|-+       |Environment|
              +-------------+         +-----------+

SQUAD is multi-team and multi-project. Each team can have multiple
projects. For each project, you can have multiple builds, and for each
build, multiple test runs. Each test run can include multiple test
results, which can be either pass/fail results, or metrics, containing
one or more measurement values. Test and metric results can belong to a
Suite, which is a basically used to group and analyze results together.
Every test suite must be associated with exactly one Environment, which
describes the environment in which the tests were executed, such as
hardware platform, hardware configuration, OS, build settings (e.g.
regular compilers vcs optimized compilers), etc. Results are always
organized by environments, so we can compare apples to apples.

Projects can have subscriptions, which are email address that should be
notified about important events such as changing test results. ProjectStatus
records the most recent build of a project, against which future results should
be compared in search for important events to notify subscribers about.

Submitting results
------------------

The API is the following

**POST** /api/submit/:team/:project/:build/:environment

-  ``:team`` is the team identifier. It must exist previously.
-  ``:project`` is the project identifier. It must exist previously.
-  ``:build`` is the build identifier. It can be a git commit hash, a
   Android manifest hash, or anything really. Extra information on the
   build can be submitted as an attachment. If a build timestamp is not
   informed there, the time of submission is assumed.
-  ``:environment`` is the environmenr identitifer. It will be created
   automatically if does not exist before.

The test data must be submitted as file attachments in the ``POST``
request. The following files are supported:

-  ``tests``: test results data
-  ``metrics``: metrics data
-  ``metadata``: metadata about the test run
- ``attachment``: arbitrary file attachments. Multiple attachments can
  be submitted by providing this parameter multiple times.

See `Input file formats <#input-file-formats>`__ below for details on
the format of the data files.

Example:

::

    $ curl \
        --header "Auth-Token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
        --form tests=@/path/to/test-rsults.json \
        --form metrics=@/path/to/metrics.json \
        --form metadata=@/path/to/metadata.json \
        --form attachment=@/path/to/screenshot.png \
        --form attachment=@/path/to/extra-info.txt \
        https://squad.example.com/api/submit/my-team/my-project/x.y.z/my-ci-env

Since test results should always come from automation systems, the API
is the only way to submit results into the system. Even manual testing
should be automated with a driver program that asks for user input, and
them at the end prepares all the data in a consistent way, and submits
it to dashboard.

Input file formats
------------------

Test results
~~~~~~~~~~~~

Test results must be posted as JSON, encoded in UTF-8. The JSON data
must be a hash (an object, strictly speaking). Test names go in the
keys, and values must be either ``"pass"`` or ``"fail"``.

Tests can be grouped in test suites. For that, the test name must be
prefixed with the suite name and a slash (``/``). Therefore, slashes are
reserved characters in this context, and cannot be used in test names.
Suite names can have embedded slashes in them; so "foo/bar" means suite
"foo", test "bar"; and "foo/bar/baz" means suite "foo/bar", test "baz".

Example:

.. code:: json

    {
      "test1": "pass",
      "test2": "pass",
      "group1/test1": "pass",
      "group1/test2": "fail",
      "group1/subgroup/test1": "pass",
      "group1/subgroup/test2": "pass"
    }

Metrics
~~~~~~~

Metrics must be posted as JSON, encoded in UTF-8. The JSON data must be
a hash (an object, strictly speaking). Metric names go in the keys, and
values must be either a single number, or an array of numbers. In the
case of an array of numbers, then their mean will be used as the metric
result; the whole set of results will be used where applicable, e.g. to
display ranges.

As with test results, metrics can be grouped in suites. For that, the
test name must be prefixed with the suite name and a slash (``/``).
Therefore, slashes are reserved characters in this context, and cannot
be used in test names. Suite names can have embedded slashes in them; so
"foo/bar" means suite "foo", metric "bar"; and "foo/bar/baz" means suite
"foo/bar", metric "baz".

Example:

.. code:: json

    {
      "v1": 1,
      "v2": 2.5,
      "group1/v1": [1.2, 2.1, 3.03],
      "group1/subgroup/v1": [1, 2, 3, 2, 3, 1]
    }


Metadata
~~~~~~~~

Metadata about the test run must be posted in JSON, encoded in UTF-8.
The JSON data must be a hash (an object). Keys and values must be
strings. The following fields are recognized:

* ``build_url``: URL pointing to the origin of the build used in the
  test run
* ``datetime``: timestamp of the test run, as a ISO-8601 date
  representation, with seconds. This is the representation that ``date
  --iso-8601=seconds`` gives you.
* ``job_id``: identifier for the test run. Must be unique for the
  project.
* ``job_status``: string identifying the status of the project. SQUAD
  makes no judgement about its value.
* ``job_url``: URL pointing to the original test run.
* ``resubmit_url``: URL that can be used to resubmit the test run.

Other fields must be submitted. They will be stored, but will not be
handled in any specific way.

CI loop integration (optional)
------------------------------

SQUAD can integrate with existing automation systems to participate in a
Continuous Integration (CI) loop through its CI subsystem. This
subsystem has the following features:

* receiving test job requests
* submitting test job requests to test execution backends
* pulling test job results from test execution backends

The data model for the CI subsystem looks like this::

   +---------+    +---------+    +------------------------+
   | TestJob |--->| Backend |--->| Backend implementation |
   +---------+    +---------+    +------------------------+
        |
        |         +---------------------+
        +-------->| TestRun (from core) |
                  +---------------------+


TestJob holds the data related to a test job request. This test job is going to
be submitted to a Backend, and after SQUAD gets results back from that backend,
it will create a TestRun object with the results data. A Backend is a
representation of a given test execution system, such as a LAVA server, or
Jenkins. ``Backend`` contains the necessary data to access the backend, such as
URL, username and password, etc, while ``Backend implementation`` encapsulates
the details on how to interact with that type of system (e.g. API calls, etc).
So for example you can have multiple backends of the same type (e.g. different
2 LAVA servers).

For the CI loop integration to work, you need to run a few extra
processes beyond the web interface. See ``INSTALL.rst`` for details.

Submitting test job requests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The API is the following

**POST** /api/submitjob/:team/:project/:build/:environment

* ``team``, ``project``, ``build`` and ``environment`` are used to
  identify which project/build/environment will be used to record the
  results of the test job.
* The following data must be submitted as POST parameters:
  * ``backend``: name of a registered backend, to which this test job
    will be submitted.
  * ``definition``: test job definition. The contents and format are
    backend-specific. If it is more convenient, the definition can also
    be submitted as a file upload instead of as a POST parameter.

Example (with test job definition as POST parameter)::

    $ DEFINITION="$(cat /path/to/definition.txt)"
    $ curl \
        --header "Auth-Token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
        --form backend=lava \
        --form definition="$DEFINITION" \
        https://squad.example.com/api/submitjob/my-team/my-project/x.y.z/my-ci-env

Example (with test job definition as file upload)::

    $ curl \
        --header "Auth-Token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
        --form backend=lava \
        --form definition=@/path/to/definition.txt \
        https://squad.example.com/api/submitjob/my-team/my-project/x.y.z/my-ci-env


Submitting test job watch requests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test job watch request are similar to test job requests. The only difference is
that some other service submitted the test job for execution and SQAD is
requested to track the progress. After test job is finished SQUAD will retrieve
the results and do post processing. The API is following:

**POST** /api/submitjob/:team/:project/:build/:environment

* ``team``, ``project``, ``build`` and ``environment`` are used to
  identify which project/build/environment will be used to record the
  results of the test job.
* The following data must be submitted as POST parameters:
  * ``backend``: name of a registered backend, to which this test job
    was be submitted.
  * ``testjob_id``: test job ID. The contents and format are
    backend-specific.

Example (with test job definition as POST parameter)::

    $ curl \
        --header "Auth-Token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
        --form backend=lava \
        --form testjob_id=123456 \
        https://squad.example.com/api/watchjob/my-team/my-project/x.y.z/my-ci-env

License
-------

Copyright © 2016-2017 Linaro Limited

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
Public License for more details.

You should have received a copy of the GNU General Public License along
with this program. If not, see http://www.gnu.org/licenses/.

.. vim: tw=72
