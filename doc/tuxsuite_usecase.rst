===================================
Use case: setup SQUAD with TuxSuite
===================================

Introduction
------------

`TuxSuite`_ is a service provided by `Linaro`_ supporting build and testing
at scale. The service can now be integrated with SQUAD via the tuxsuite backend.

SQUAD supports TuxSuite by pulling tests and builds results from the API. Keep in mind
that SQUAD WILL NOT submit job requests to TuxSuite, as it does for LAVA backends.

.. _`TuxSuite`: https://tuxsuite.com
.. _`Linaro`: https://linaro.org


Creating a Backend for a TuxSuite instance
--------------------------------------

Log in into SQUAD admin view (``/admin``) and access ``ci > backends > add backend``
for inclusion form. Fill up accordingly:

- name: name of the backend. Example: tuxsuite.com
- url: it's how SQUAD will communicate with TuxSuite. Example: https://tuxsuite.com/v1/
- username and token: these are used by other backends type for authentication. Fill it in with "notused" for example.
- implementation type: leave it as ``tuxsuite``
- backend settings: used to spare specific settings for TuxSuite instances. For details see :ref:`backend_settings_ref_label` 
- poll interval: number of minutes to wait before fetching a job from TuxSuite
- max fetch attempts: max number of times SQUAD will attempt to fetch a job from TuxSuite
- poll enabled: if this is disabled SQUAD will not try to poll jobs from TuxSuite


Creating a Project in SQUAD
---------------------------

SQUAD needs minimal data to start working with TuxSuite: Group and Project.
By logging in the admin view, go to ``core > groups > add`` to add a new
group and ``core > projects > add`` to add a new project. These are trivial
to create, but please feel free to contact us if any help is needed.


Submitting and fetching test jobs
---------------------------------

Given that all steps above are working correctly, you are ready to submit your
first job through SQUAD. You can learn from TuxSuite documentation how to send
build and test requests. For the sake of simplicity, we'll stick to one of LKFT's
pipelines sample and use it to compile a Linux Kernel. Then we'll make up the job_id
to send to SQUAD's API for fetching::

    tuxsuite build-set \
         --git-repo https://gitlab.com/Linaro/lkft/mirrors/stable/linux-stable-rc \
	 --git-sha 7ec6d8ae728e2f3b91a4cfac5e664ca32eb213da \
	 --tux-config https://gitlab.com/Linaro/lkft/pipelines/lkft-common/-/raw/master/tuxconfig/linux-5.17.y.yml \
	 --set-name arm64-clang-12 \
	 --json-out build.json

    cat build.json
    ...
         "uid": "2843VDPeVhg4yaTkgTur0T3ykmq",
         "project": "linaro/lkft",
    ...
	 
    curl localhost:8000/api/watchjob/<group-slug>/<project-slug>/<build-version>/<env> \
         --header "Authorization: token $SQUAD_TOKEN" \
         --form "backend=tuxsuite.com" \
         --form "job_id=BUILD:linaro@lkft#2843VDPeVhg4yaTkgTur0T3ykmq"

Where ``group-slug`` and ``project-slug`` are the ones created in steps above, whereas
``build-version`` and ``env`` do not need to exist before submitting a job. For clarification ``buid-version``
is usually a git-commit hash and ``env`` is commonly the architecture of the build.
Although it's not covered in this tutorial, creating a ``squad-token`` is straightforward, do so
by logging into admin view and go to ``auth token > tokens > add`` to add an auth token for a user.
Lastly, ``backend-name`` is the one created in the sections above.
