=================================
CI: continous integration support
=================================

.. _ci_ref_label:

CI module in SQUAD
------------------

Thissubsystem has the following features:

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
processes beyond the web interface. See :ref:`install_python` for details.

.. _ci_job_ref_label:

Submitting test job requests
----------------------------

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

.. _ci_watch_ref_label:

Submitting test job watch requests
----------------------------------

Test job watch request are similar to test job requests. The only difference is
that some other service submitted the test job for execution and SQUAD is
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

Backend settings
----------------

Backends support internal settings that are stored in the database. It is
assumed that settings are a valid YAML markup.

Supported backends
------------------

Out of the box SQUAD supports following backends:
 - `LAVA <https://validation.linaro.org/static/docs/v2/>`_ 

LAVA
~~~~

LAVA backend supports the following settings:
 - CI_LAVA_INFRA_ERROR_MESSAGES
   a list of strings that cause automated job resubmission when matched
   in the LAVA error message
 - CI_LAVA_SEND_ADMIN_EMAIL
   boolean flag that prevents sending admin emails for each resubmitted
   job when set to ``False``

Example LAVA backend settings:

.. code-block:: yaml

    CI_LAVA_INFRA_ERROR_MESSAGES:
      - 'Connection closed'
      - 'lava_test_shell connection dropped.'
      - 'fastboot-flash-action timed out'
      - 'u-boot-interrupt timed out'
      - 'enter-vexpress-mcc timed out'
      - 'Unable to fetch git repository'
    CI_LAVA_SEND_ADMIN_EMAIL: False

.. vim: ts=4 sw=4 et=1
