=================================
CI: continous integration support
=================================

.. _ci_ref_label:

CI module in SQUAD
------------------

This subsystem has the following features:

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
processes beyond the web interface. See :ref:`production_install_ref_label` for details.

.. _ci_job_ref_label:

Submitting test job requests
----------------------------

The API is the following

**POST** /api/submitjob/:group/:project/:build/:environment

* ``group``, ``project``, ``build`` and ``environment`` are used to
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
        https://squad.example.com/api/submitjob/my-group/my-project/x.y.z/my-ci-env

Example (with test job definition as file upload)::

    $ curl \
        --header "Auth-Token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
        --form backend=lava \
        --form definition=@/path/to/definition.txt \
        https://squad.example.com/api/submitjob/my-group/my-project/x.y.z/my-ci-env

.. _ci_watch_ref_label:

Submitting test job watch requests
----------------------------------

Test job watch request are similar to test job requests. The only difference is
that some other service submitted the test job for execution and SQUAD is
requested to track the progress. After test job is finished SQUAD will retrieve
the results and do post processing. The API is following:

**POST** /api/submitjob/:group/:project/:build/:environment

* ``group``, ``project``, ``build`` and ``environment`` are used to
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
        https://squad.example.com/api/watchjob/my-group/my-project/x.y.z/my-ci-env

.. _`backend_settings_ref_label`:

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

SQUAD supports only LAVA v2. Old version of LAVA was made obsolete with 2017.11
LAVA release.

LAVA backend supports the following settings:
 - CI_LAVA_INFRA_ERROR_MESSAGES
   a list of strings that cause automated job resubmission when matched
   in the LAVA error message
 - CI_LAVA_SEND_ADMIN_EMAIL
   boolean flag that prevents sending admin emails for each resubmitted
   job when set to ``False``
 - CI_LAVA_HANDLE_SUITE
   boolean flag that parses results from LAVA test suite when
   set to ``True``. Please note that this option can be overwritten by
   having the same option with different value in Project `project_settings`
 - CI_LAVA_CLONE_MEASUREMENTS
   boolean flag that allows to save LAVA result as both Test and Measurement
   when set to ``True``. Default is ``False``. Can be overwritten for each
   project separately (similar to CI_LAVA_HANDLE_SUITE).
 - CI_LAVA_HANDLE_BOOT
   boolean flag that parses LAVA `auto-login-action` as a boot
   test when set to ``True``. Default is ``False``. Can be overwritten for
   each project separately (similar to CI_LAVA_HANDLE_SUITE). **NOTE**:
   Before SQUAD 1.x series, the default behavior was to always process
   `auto-login-action` as boot. After 1.x, the default behavior has changed
   to do the opposite.

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
    CI_LAVA_HANDLE_SUITE: True

Multinode
+++++++++

SQUAD supports fetching results from LAVA multinode jobs. There are however
a few limitations with this setup:
 - All results from multinode will share environment name
   Since test jobs are submitted via SQUAD using the environment from submit
   URL there is no way for SQUAD to distinguish between different environmens
   on different parts of multinode job.
 - Resubmit will repeat the whole set
   In SQUAD all parts of multinode job will share the multinode definition.
   For this reason re-submitting any part of the multinode job will result
   in new multinode job that includes all parts.
 - Each part of the multinode job will be retrieved separately
   This means that each part will create a TestRun in SQUAD. This should not
   be a major issue as all results will still be available. Users need to make
   sure that the test names don't overlap as SQUAD will not have any means of
   distinguishing between identically named tests from different parts of
   multinode job.

.. vim: ts=4 sw=4 et=1
