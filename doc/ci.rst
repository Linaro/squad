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
