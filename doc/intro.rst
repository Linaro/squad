==================================
Introduction: data model and usage
==================================

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

SQUAD is multi-group and multi-project. Each group can have multiple
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

Projects can have subscriptions, which are either users or manually-entered
email addreses that should be notified about important events such as changing
test results. ProjectStatus records the most recent build of a project, against
which future results should be compared in search for important events to
notify subscribers about. SQUAD also supports a metric threshold system, which
will send notification to project subscribers if the test result metrics exceed
a certain value. The threshold values will also appear in the charts. Projects 
have the `project_settings` field for any specific configuration it might require.

.. _result_submit_ref_label:

Submitting results
------------------

The API is the following

**POST** /api/submit/:group/:project/:build/:environment

-  ``:group`` is the group identifier. It must exist previously.
-  ``:project`` is the project identifier. It must exist previously.
-  ``:build`` is the build identifier. It can be a git commit hash, a
   Android manifest hash, or anything really. Extra information on the
   build can be submitted as an attachment. If a build timestamp is not
   informed there, the time of submission is assumed.
-  ``:environment`` is the environmenr identitifer. It will be created
   automatically if does not exist before.

All of the above identifiers (``:group``, ``:project``, ``:build``, and
``:environment``) must match the regular expression
``[a-zA-Z0-9][a-zA-Z0-9_.-]*``.

The test data files must be submitted as either file attachments, or as
regular ``POST`` parameters.  . The following files are supported:

-  ``tests``: test results data
-  ``metrics``: metrics data
-  ``metadata``: metadata about the test run
- ``attachment``: arbitrary file attachments. Multiple attachments can
  be submitted by providing this parameter multiple times.

See `Input file formats <#input-file-formats>`__ below for details on
the format of the data files.

Example with test data as file uploads::

    $ curl \
        --header "Auth-Token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
        --form tests=@/path/to/test-results.json \
        --form metrics=@/path/to/metrics.json \
        --form metadata=@/path/to/metadata.json \
        --form log=@/path/to/log.txt \
        --form attachment=@/path/to/screenshot.png \
        --form attachment=@/path/to/extra-info.txt \
        https://squad.example.com/api/submit/my-group/my-project/x.y.z/my-ci-env

Example with test data as regular ``POST`` parameters::

    $ curl \
        --header "Auth-Token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
        --form tests='{"test1": "pass", "test2": "fail"}' \
        --form metrics='{"metric1": 21, "metric2": 4}' \
        --form metadata='{"foo": "bar", "baz": "qux"}' \
        --form log='log text ...' \
        --form attachment=@/path/to/screenshot.png \
        --form attachment=@/path/to/extra-info.txt \
        https://squad.example.com/api/submit/my-group/my-project/x.y.z/my-ci-env

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
keys, and values must be either ``"pass"`` or ``"fail"``. Case does not
matter, so ``"PASS"``/``"FAIL"`` will work just fine. Any value that
when downcased is not either ``"pass"`` or ``"fail"`` will be mapped to
``None``/``NULL`` and displayed in the UI as *skip*.

Tests can be grouped in test suites. For that, the test name must be
prefixed with the suite name and a slash (``/``). Therefore, slashes are
reserved characters in this context, and cannot be used in test names.
There is one exception to this rule. If test name contains square brackets
(``[``, ``]``) they are considered as test variant. The string inside
brackets can contain slashes. Suite names can have embedded slashes in
them; so "foo/bar" means suite "foo", test "bar"; and "foo/bar/baz" means
suite "foo/bar", test "baz".

Example:

.. code:: json

    {
      "test1": "pass",
      "test2": "pass",
      "testsuite1/test1": "pass",
      "testsuite1/test2": "fail",
      "testsuite2/subgroup1/testA": "pass",
      "testsuite2/subgroup2/testA": "pass",
      "testsuite2/subgroup2/testA[variant/one]": "pass",
      "testsuite2/subgroup2/testA[variant/two]": "pass"
    }

There is an alternative format for sending results. Since SQUAD supports
storing test log in the Test object, passed JSON file can look as follows:

.. code:: json

    {
      "test1": {"result": "pass", "log": "test 1 log"},
      "test2": {"result": "pass", "log": "test 2 log"},
      "testsuite1/test1": {"result": "pass", "log": "test 1 log"},
      "testsuite1/test2": {"result": "fail", "log": "test 2 log"}
    }

Both forms are supported. In case log entry is missing or simple JSON
format is used, logs for each Test object are empty. They can be filled
in using plugins.

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
* ``suite_versions``: a dictionary with version number strings for suite names
  used in the tests and metrics data. For example, if you have test suites
  called "foo" and "bar", their versions can be expressed having metadata that
  looks like this::

    {
        # ...
        "suite_versions": {
            "foo": "1.0",
            "bar": "3.1"
        }
    }

If a metadata JSON file is not submitted, the above fields can be
submitted as POST parameters. If a metadata JSON file is submitted, no
POST parameters will be considered to be used as metadata.

When sending a proper metadata JSON file, other fields may also be
submitted. They will be stored, but will not be handled in any specific
way.


CI loop integration (optional)
------------------------------

SQUAD can integrate with existing automation systems to participate in a
Continuous Integration (CI) loop through its CI subsystem. For more details
check :ref:`ci_ref_label`.
