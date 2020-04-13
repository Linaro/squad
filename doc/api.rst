=============================
API: Interacting with backend
=============================

Available APIs
--------------

SQUAD has a set of APIs that allow to interact with it's backend. There
are two main parts of the API

- Native API
  This is meant to provide main features of SQUAD (submitting results,
  submitting CI test jobs)
- REST API
  Provides access to almost all properties of core data model objects. Also
  provides additional features that can be used to build alternative
  frontends or automated tools.

Native APIs
-----------

data
~~~~

**GET** /api/data/<group_slug>/<project_slug>/

Retrieves metrics data in JSON format. The following parameters are mandatory:

- `metric`: which metric to retrieve. You have to use the full metric name,
  i.e. `<suite_slug>/<metric_slug>`.

  This parameter can be specified multiple times, so data from multiple metrics
  can be fetched with a single request.

- `environment`: environment for which metric data is to be retrieved.

  This parameter can be specified multiple times, so data from multiple
  environments can be fetched with a single request.

- `format`: format of response. Valid values are `json` and `csv`. If this
  parameter is ommited, `json` is used as a default.

The JSON response is an object, which metrics as keys. Values are also objects,
which environments as keys, and the data series as values. Each data point is
an array with 3 values: the build date timestamp (as the number of seconds
since the epoch), the value of the metric, and the build identifier.

Example::

    {
        "mysuite/mymetric": {
            "environment1": [
                [1537210872, 1.15, "v0.50.1-21-g7b96236"],
                [1537290845, 1.14, "v0.50.1-22-g1097312"],
                [1537370812, 1.13, "v0.50.1-23-g0127321"],
                [1537420892, 1.15, "v0.50.1-24-g8262524"],
                [1537500801, 1.13, "v0.50.1-25-gfa72526"],
                // [...]
            ],
            "environment2": [
                [1537210872, 1.25, "v0.50.1-21-g7b96236"],
                [1537290845, 1.24, "v0.50.1-22-g1097312"],
                [1537370812, 1.23, "v0.50.1-23-g0127321"],
                [1537420892, 1.25, "v0.50.1-24-g8262524"],
                [1537500801, 1.23, "v0.50.1-25-gfa72526"],
                // ...
            ]
        },
        "mysuite/anothermetric": {
            // [...]
        }
    }

The CSV response contains one line for each data point. The columns are:
metric, environment, timestamp, value, build identifier. Assuming the same data
as the JSON example above, the CSV would look like this::

    "mysuite/mymetric","environment1","1537210872","1.15","v0.50.1-21-g7b96236"
    "mysuite/mymetric","environment1","1537290845","1.14","v0.50.1-22-g1097312"
    "mysuite/mymetric","environment1","1537370812","1.13","v0.50.1-23-g0127321"
    "mysuite/mymetric","environment1","1537420892","1.15","v0.50.1-24-g8262524"
    "mysuite/mymetric","environment1","1537500801","1.13","v0.50.1-25-gfa72526"
    [...]
    "mysuite/mymetric","environment2","1537210872","1.25","v0.50.1-21-g7b96236"
    "mysuite/mymetric","environment2","1537290845","1.24","v0.50.1-22-g1097312"
    "mysuite/mymetric","environment2","1537370812","1.23","v0.50.1-23-g0127321"
    "mysuite/mymetric","environment2","1537420892","1.25","v0.50.1-24-g8262524"
    "mysuite/mymetric","environment2","1537500801","1.23","v0.50.1-25-gfa72526"
    [...]
    "mysuite/anothermetric",[...]
    [...]


createbuild
~~~~~~~~~~~

**POST** /api/createbuild/<group_slug>/<project_slug>/<version_string>

Creates Build object. Following parameters are accepted:

- patch_source - string matching PatchSource.name
- patch_baseline - version string matching Build.version
- patch_id - string identifying the patched version (for example git commit ID)

submit
~~~~~~

:ref:`result_submit_ref_label`.

submitjob
~~~~~~~~~

:ref:`ci_job_ref_label`.

watchjob
~~~~~~~~

:ref:`ci_watch_ref_label`.

resubmit
~~~~~~~~

**POST** /api/resubmit/<job_id>

This API is only available to superusers at the moment. It allows to resubmit
CI test jobs using Backend's implementation.

forceresubmit
~~~~~~~~~~~~~

**POST** /api/forceresubmit/<job_id>

This API is only available to superusers at the moment. It allows to resubmit
CI test jobs using Backend's implementation. Works similarly to 'resubmit' but
doesn't respect 'can_resubmit' flag on the TestJob object.

REST APIs
---------

The REST API is powered by `Django Rest Framework (DRF)<https://www.django-rest-framework.org/>`_ and
`Django fields lookups <https://docs.djangoproject.com/en/3.0/topics/db/queries/#field-lookups>`_.
This means that for supported endpoints you can do a field lookup. For example,
querying all testruns that belong to a build that belongs to a project called
MyProject, one would run a query like:

**GET** /api/testruns/?build__project__name=MyProject

This gives the API flexibility for filtering in many different ways.

groups (/api/groups/)
~~~~~~~~~~~~~~~~~~~~~

Provides access to Group object. This object corresponds to SQUAD Group
(not to be confused with Django group). The Group objects can be filtered
and searched. Both operations can be done using 'name' and 'slug' fields.

With enough privileges Groups can also be created, modified and deleted
using REST API with POST, PUT and DELETE HTTP requests respectively

projects (/api/projects/)
~~~~~~~~~~~~~~~~~~~~~~~~~

Provides access to Project object. In case of private projects token with
enough privileges is required to access the object. Project API endpoint has
following additional routes:

- builds (/api/projects/<id>/builds/)

  Provides list of builds associated with this project. List is paginated
- test_results (/api/projects/<id>/test_results/)

  Provides list of latest results for given test for all environments.
  'test_name' is a mandatory GET parameter for this call. List is paginated.
  It is advised to limit the search results to 10 to avoid poor performance.
  This can be achieved using 'limit=10' GET parameter

- subscribe (/api/projects/<id>/subscribe/)

  Provides means to subscribe either email address or user to the project
  notifications in automated way. This endpoint expects POST request with
  single field "email"

- unsubscribe (/api/projects/<id>/unsubscribe/)

  Provides means to unsubscribe either email address or user from the project
  notifications in automated way. This endpoint expects POST request with
  single field "email"

With enough privileges Projects can also be created, modified and deleted
using REST API with POST, PUT and DELETE HTTP requests respectively

builds (/api/builds/)
~~~~~~~~~~~~~~~~~~~~~

Provides access to Build object. In case of private projects token with
enough privileges is required to access the object. Build API endpoint has
following additional routes:

- metadata (/api/builds/<id>/metadata/)

  Provides list of all metadata key-value pairs associated with this object
- status (/api/builds/<id>/status/)

  Provides access to ProjectStatus object associated with this object
- testruns (/api/builds/<id>/testruns)

  Provides list of TestRun objects associated with this object
- testjobs (/api/builds/<id>/testjobs/)

  Provides list of TestJob objects associated with this object
- email (/api/builds/<id>/email/)

  Provides contents of email notification that would be generated for this object.
  Content is generated using either EmailTemplate associated with the Project
  or a custom one. The EmailTemplate has to be defined in SQUAD database before
  API is called. The route takes the following GET parameters:

  - output - mime type to be generated. Defaults to "text/plain". Can also be set
    to "text/html". Using HTML requires HTML part of the EmailTemplate to be defined

  - template - ID of the EmailTemplate to be used
  - baseline - ID of the Build object to be used as comparison baseline. The default
    is "previous finished" build in the same project.
  - force - if set to true invalidates cached object. Default is false

- report (/api/build/<id>/report/)

  This API accepts both GET and POST requests.

  Provides non blocking version of 'email' API. Both calls will produce DelayedReport
  objects which cache the results of the call. Non blocking version ('report')
  is recommended as it is executed in separate process on the worker node and
  doesn't affect web frontend performance or memory consumption. Reports might be
  resource hungry and long running which causes webserver requests to time out.
  Non blocking call returns immediately returning url to the cached resource.
  Final results can be retrieved by:

  - email notification
  - callback notification
  - polling the result URL - Results are completed when 'status_code' field
    is filled in (not None/Null)

  'report' API has following options:

  - output - mime type to be generated. Defaults to "text/plain". Can also be set
    to "text/html". Using HTML requires HTML part of the EmailTemplate to be defined

  - template - ID of the EmailTemplate to be used
  - baseline - ID of the Build object to be used as comparison baseline. The default
    is "previous finished" build in the same project.
  - email_recipient - email address which is notified when report is ready
  - callback - URL which SQUAD calls when report is ready. Call is made using POST
    request type. Call can be secured with token
  - callback_token - token/password for securing callback. When "callback" option
    is present it adds "Authorization" and "Auth-Token" headers to the HTTP POST
    call. It is recommended to send this option usig POST request to avoid password
    leakage.
  - keep - number of days to keep the cached reports in the database
  - force - if set to true invalidates cached object. Default is false

With enough privileges Builds can also be created, modified and deleted
using REST API with POST, PUT and DELETE HTTP requests respectively. This is
however not recommended.

testjobs (/api/testjobs/)
~~~~~~~~~~~~~~~~~~~~~~~~~

Provides access to TestJob object. In case of private projects token with
enough privileges is required to access the object. Build API endpoint has
following additional routes:

- definition

  Returns plain text version of the TestJob.definition field. This is pretty specific
  to LAVA but doesn't exclude any other automated execution tools.

testruns (/api/testruns/)
~~~~~~~~~~~~~~~~~~~~~~~~~

Provides access to TestRun object. In case of private projects token with
enough privileges is required to access the object. Build API endpoint has
following additional routes:

- tests_file (/api/testruns/<id>/tests_file/)
- metrics_file (/api/testruns/<id>/metrics_file/)
- metadata_file (/api/testruns/<id>/metadata_file/)
- log_file (/api/testruns/<id>/log_file/)
- tests (/api/testruns/<id>/tests/)
- metrics (/api/testruns/<id>/metrics/)
- status (/api/testruns/<id>/status/)

  Provides a list of TestRun's statuses. One can also passing in filters to
  get specific results, e.g. /api/testruns/<id>/status/?suite__isnull=true
  retrieves the overall Status object for that testrun.

tests (/api/tests/)
~~~~~~~~~~~~~~~~~~~

Provides access to Tests objects. In case of private projects token with
enough privileges is required to access the objects.

metrics (/api/metrics/)
~~~~~~~~~~~~~~~~~~~

Provides access to Metrics objects. In case of private projects token with
enough privileges is required to access the objects.

suites (/api/suites/)
~~~~~~~~~~~~~~~~~~~~~

Provides access to Suite object. In case of private projects token with
enough privileges is required to access the object.

environments (/api/environments/)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides access to Environment object. In case of private projects token with
enough privileges is required to access the object.

backends (/api/backends/)
~~~~~~~~~~~~~~~~~~~~~~~~~

Provides access to Backend object.

With enough privileges Backend can also be created, modified and deleted
using REST API with POST, PUT and DELETE HTTP requests respectively

emailtemplates (/api/emailtemplates/)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides access to EmailTemplate object.

With enough privileges EmailTemplate can also be created, modified and deleted
using REST API with POST, PUT and DELETE HTTP requests respectively

knownissues (/api/knownissues/)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides access to KnownIssue object.

With enough privileges KnownIssue can also be created, modified and deleted
using REST API with POST, PUT and DELETE HTTP requests respectively

patchsources (/api/patchsources/)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides access to PatchSource object.

annotations (/api/annotations/)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides access to Annotation object.

With enough privileges Annotation can also be created, modified and deleted
using REST API with POST, PUT and DELETE HTTP requests respectively

metricthresholds (/api/metricthresholds/)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides access to MetricThreshold object.

With enough privileges MetricThreshold can also be created, modified and deleted
using REST API with POST, PUT and DELETE HTTP requests respectively

reports (/api/reports/)
~~~~~~~~~~~~~~~~~~~~~~~

Provides access to results of /api/build/<id>/email and /api/build/<id>/report
results. Both of these endpoints create DelayedReport objects and present
them to the user. The difference is that 'email' API is blocking and 'report'
is not blocking (returns immediately).

status_code field in the reports endpoint will indicate whether the report is
ready. If the field is empty, the report wasn't prepared yet. status_code follows
the HTTP status codes. Anything else that 200 in status_code field suggests
a problem. error_message field can be checked to learn about issue details.

REST API Schema (for CLI)
-------------------------

SQUAD's API supports API clients. Example is coreapi. In order for client
to understand the API SQUAD generates schema file. Schema is dynamically
built and it's available at /api/schema URL. Example usage with coreapi-cli:

::

  coreapi get https://<host_tld>/api/schema
  coreapi action projects list

More details about coreapi can be found on coreapi website and DRF website:

 * http://www.coreapi.org/
 * https://www.django-rest-framework.org/topics/api-clients/

SQUAD-Client
-------------------------

SQUAD team has been working on a client tool that help users query the API
easily, using a Python descriptive way of interacting with the backend.

If you are interested in using such tool, please check it out in
`SQUAD-Client <https://github.com/Linaro/squad-client>`_

Badges
------

SQUAD offers project and build badges that can be used in the webpages

::

  https://<squad_instance_tld>/group/project/badge
  https://<squad_instance_tld>/group/project/build_version/badge

The colour of the badge matches the passed/failed condition.
Following colours are presented:

  * green (#5cb85c) when there are no failed results
  * orange (#f0ad4e) when there are both passed and failed results
  * red (#d9534f) when there are no passed results

If there are no results, the badge colour is grey (#999)

Badge offers customization through following parameters:

- title

  Changes the left part of the badge to a custom text

- passrate

  Changes the right part of the badge to use pass rate rather than number
  of tests passed, failed and skipped

- metrics

  Changes the right part of the badge to use metrics instead of test results.
  In such case badge colour is set to green. In case both 'metrics' and
  'passrate' keywords are present, 'metrics' is ignored.

Google Data Studio
------------------

SQUAD has an implementation of the Google Data Studio Community Connector under
https://github.com/Linaro/squad/tree/master/scripts/community_connector/
There is also an existing deployment which will pull data from
https://qa-reports.linaro.org/ and resides in this location (it is currently
restricted to Linaro members):

::

   https://datastudio.google.com/datasources/create?connectorId=AKfycbxnkmVPXZRad22brXQ6BIB3iG9-GPWbjZnXds0vTuU

SQUAD Connector takes three arguments, token, group and project. The token
argument is not required but then the dataset will be limited as for the
non-authenticated user.
After connecting it will display all the environments as metrics in the Data
Studio, and it will use date and SQUAD metrics as dimensions. User can use
this data to create reports and dashboards in the Google Data Studio as they
see fit.

User is also free to deploy an instance of the Connector of their own using the
code and manifest presented in the codebase.
