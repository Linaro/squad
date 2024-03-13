===============================
Use case: setup SQUAD with LAVA
===============================

Introduction
------------

Once SQUAD installation is complete, a typical use case would be integrating
it with a LAVA instance. The purpose of this use case is to describe a
step-by-step set up of SQUAD with LAVA to submit and fetch jobs. If you haven't
yet set up SQUAD, take a step back and follow :ref:`production_install_ref_label`


Setting up a LAVA instance
--------------------------

LAVA has its own extensive documentation on how to get a server up and running.
If you don't have it already, please refer to `LAVA installation`_ to configure
yourself one. From this point it's taken that you have enough access to a
running LAVA v2 instance that jobs can be submitted to and fetched from.


:Note:
 Make sure that your LAVA instance has ``event notifications`` enabled,
 as it is disabled by default. See `LAVA event notifications`_ for details.


.. _`LAVA installation`: https://validation.linaro.org/static/docs/v2/installing_on_debian.html#debian-installation
.. _`LAVA authentication tokens`: https://validation.linaro.org/static/docs/v2/first_steps.html?highlight=token#authentication-tokens
.. _`LAVA event notifications`: https://validation.linaro.org/static/docs/v2/data-export.html#event-notifications


Creating a Backend for a LAVA instance
--------------------------------------

Log in into SQUAD admin view (``/admin``) and access ``ci > backends > add backend``
for inclusion form. Fill up accordingly:

- name: name of the backend. Example: validation.linaro.org
- url: LAVA RPC2 endpoint, it's how SQUAD will communicate with LAVA. Example: https://validation.linaro.org/RPC2
- username: a LAVA user with enough access to submit jobs
- token: a generated token for the user above, used to securely connect to the LAVA instance. See `LAVA authentication tokens`_ for details
- implementation type: leave it as ``lava``
- backend settings: used to spare specific settings for LAVA instances. For details see :ref:`backend_settings_ref_label` 
- poll interval: number of minutes to wait before fetching a job from LAVA
- max fetch attempts: max number of times SQUAD will attempt to fetch a job from LAVA
- poll enabled: if this is disabled SQUAD will not try to poll jobs from LAVA 


Creating a Project in SQUAD
---------------------------

SQUAD needs minimal data to start working with LAVA: Group and Project.
By logging in the admin view, go to ``core > groups > add`` to add a new
group and ``core > projects > add`` to add a new project. These are trivial
to create, but please feel free to contact us if any help is needed.


Submitting and fetching test jobs
---------------------------------

Given that all steps above are working correctly, you are ready to submit your
first job through SQUAD. You can learn from LAVA documentation how to write
new test definitions or use existing ones. For the sake of simplicity,
we'll stick to `LAVA's example of first job`_ and use it to call SQUAD
api for submitting a new test job::

    wget https://validation.linaro.org/static/docs/v2/examples/test-jobs/qemu-pipeline-first-job.yaml
    curl localhost:8000/api/submitjob/<group-slug>/<project-slug>/<build-version>/<env> \
         --header "Auth-Token: $SQUAD_TOKEN" \
         --form "backend=<backend-name>" \
         --form "definition=@qemu-pipeline-first-job.yaml"

Where ``group-slug`` and ``project-slug`` are the ones created in steps above, whereas
``build-version`` and ``env`` do not need to exist before submitting a job. For clarification ``buid-version``
is usually a git-commit hash and ``env`` is commonly the board target that a job is running.
Although it's not covered in this tutorial, creating a ``squad-token`` is straightforward, do so
by logging into admin view and go to ``auth token > tokens > add`` to add an auth token for a user.
Lastly, ``backend-name`` is the one created in the sections above.


.. _`LAVA's example of first job`: https://validation.linaro.org/static/docs/v2/first-job.html

Extra use cases
---------------

The example above showed a simplistic SQUAD instance working along with a LAVA
one. More can be done by using SQUAD's backend API to transform it into a proxy
between a CI system (e.g. Jenkins) and a LAVA server. An instance of SQUAD is
currently running at https://qa-reports.linaro.org and its set up is fully
automated through ansible scripts at https://github.com/Linaro/qa-reports.linaro.org.

