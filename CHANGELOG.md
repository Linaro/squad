# 1.6

This 1.6 release adds support to queue suffix names, which enables
fixing a bug that happens if SQUAD was configured with AWS SQS and
a lab entered in maintenance state.

It also adds the ability to switch test results layout when viewing
a build home page.

Complete list of changes going in:

* ci: backend: lava: add exception when a lava backend is offline
* frontend:
  * build: add option to change test results layout
  * views: order environments columns by alphabetical order
* settings:
  * fix notification tasks routing
  * add support to suffix-named queues

# 1.5

This 1.5 release fixes a bug that made SQUAD submit a single
TestJob multiple times. It also allows project admins to create
copies of projects with the `Save as` option.

Complete list of changes going in:

* ci: tasks: avoid multiple submissions
* core: admin: enable `save as` option for projects
* frontend: project_settings: add advanced settings tab
* Updated translation:
  * Translated using Weblate (Norwegian Bokmål)


# 1.4

This 1.4 release fixes a bug when viweing all test results page and
enables more filteting options for build and testrun api endpoints.

Complete list of changes going in:

* api:
  * rest: enable filtering testruns by 'completed'.
  * rest: enable created date filtering on for builds in api
* frontend:
  * tests: remove unecessary ordering
  * tests: reduce queries to list tests
  * tests: simplify count of pages
  * tests: remove duplicate queries to metadata
  * tests: fix bug when listing tests without metadata

# 1.3.1

This 1.3.1 release includes a minor bug in the api and support to work
with AWS SQS:

* settings:
  * add support to custom polling interval
  * add support to prefix-named queues
  * turn on debug only when needed
* api: fix URL pattern for api/ paths
* http: authenticate users before checking permissions
* Add coverage testing with pytest

# 1.3

This 1.3 release fixes a 500 http error code when accessing linux-log-parser
tests, also improving its log detection, including `WARNINGS`.

The release also fixes some minor issues related to docker setup, among
other new features and fixes that you can see in the full log below:

* core:
  * test_history: handle tests with no metadata
  * plugins: linux_log_parser: improve kernel log parsing
* frontend: reduce query time fetching metric names
* misc:
  * debug: add django debug toolbar
  * doc: add firewall note when running on docker
  * Dockerfile: ignore version constraints from requirements.txt

# 1.2

This 1.2 release fixes a couple of performance issues when fetching testjobs
from backends and when using the REST api, among other small fixes.

It stops ignoring duplicated tests for same environments and test suites
when calculating build summary (e.g. number of passing and failing tests).
Instead, use partial summaries already calculated for test runs.

We tweaked the backend code that fetches tests before calculating
regressions and fixes. If a build had a significant high number of test runs
it would make comparison much slower. So we avoid querying all test runs at
once when running `TestComparison`.

There were changes in the backend code of the REST api that reduced the number
of trips to db, making some endpoints load faster.

Complete changelog below:

* core:
  * comparison: remove the use of iterator over tests
  * comparison: filter tests by chunks of testruns
  * comparison: fetch only id from testruns
  * comparison: filter tests by testrun ids
  * comparison: prefetch known issues
  * comparison: lowered number of testruns chunk
  * tasks: ReceiveTestRunData: ignore tests and metrics with long names
  * models: remove duplicate call to build.finished
  * test_summary: simplify summary calculation
  * project: reduce amount of trips to database
  * environment: set default expected_test_runs to zero
  * build: make finished false when no jobs or testruns
  * migrations: add missing migration for Django upgrade
  * Group: sort aggregate query explicitly
  * plugins: ignore most parameters
* ci:
  * lava: handle unicode errors gracefully
  * lava: fetch jobs right away
  * listener: respect Backend listen_enabled
  * Backend: add listen_enabled attribute
* doc:
  * fix typo in .readthedocs.yml
  * add configuration for readthedocs build
* api:
  * disable post forms
  * rest: reduce amount of queries and speed up some queries
  * utils: remove duplicate DRF backend
  * rest: avoid queries containing all projects
  * rest: test: reduce number of queries in the database
  * rest: remove deprecation warnings against django-filters 2.x
* Added translations:
  * French
* misc:
  * worker: don't constrain concurrency by default
  * squad.urls: replace deprecated shortcut function
  * tests: remove unecessary usage of Django's TestCase class
  * core, ci: stop pytest from confusing our Test* classes with tests
  * test_test: avoid pytest confusing helper method with a test
  * pytest.ini: add pytest configuration

# 1.1

* ci/lava: replace concatenation with StringIO
* settings: split tasks to separate queues
* requirements.txt: fix minimal version for pyyaml
* squad.run.worker: listen on all configured queues by default
* doc: document how to manage different queues

# 1.0.3

* api: utils: add CursorPaginationWithPageSize
* Added translation using Weblate (French)
* ci/lava: adjust hangling of malformed logs yaml for newer PyYAML
* ci/lava: resubmit: exit early
* ci/lava: extract handling of failed submissions
* ci/lava: resubmit: handle errors on the LAVA side
* api: resubmit: handle submission errors gracefully
* ci: lava: speed up conversion of YAML of logs to pain text

# 1.0.2

This release fixes a small issue with the gerrit plugin that
attempts to send notification with malformed patch_id

Complete changelog below:

* plugins:
  * plugins: gerrit: check patch_id before sending notification
* Updated transations:
  * French (updated)

# 1.0.1

* `yaml_validator`: drop usage of simple yaml.load
* api: ci: fix definition file encoding
* Updated translations:
  * Polish (completed)
  * French (added)

# 1.0

This 1.0 release marks the availability of a feature set that we envisioned
back when squad was started. We still have a lot to improve, though, so we will
continue to work on new features and improvements.

This release also brings compatibility with Django 2, which we now use by
default. However, using with Django 1 is still supported. We recommend Python
3.6 or newer.

Since we are bumping the major version number, we are also making two
backwards-incompatible changes that you need to be aware of:

* Test results from incomplete jobs are now completely ignored.
* The LAVA CI backend used to map the success of the "auto-login-action" from a
  lava job to a test called "boot". This is now ignored by default. If you rely
  on this, you can re-enable this behavior by setting `CI_LAVA_HANDLE_BOOT` in
  your project settings (only available in the Django admin interface for the
  moment). See the documentation for details.

Below, you will find a summary of the changes in this release.

* frontend:
  * frontend: templatetags: add str to global functions for templating
  * frontend: compare-project: refactor project comparison UI
  * frontend: compare-project: order projects alphanumerically
  * frontend: compare-project: compare different builds
  * frontend: filter comparison by transitions
  * frontend: fix compare projects submit
  * frontend: shrink transitions filter table
  * frontend: translation: translate django templates
  * frontend: `test_history`: fix broken javascript
* api:
  * api: rest: add ComplexFilterBackend to GroupViewSet
  * api: rest: give write only access to _password field
* ci:
  * ci: ignore all results from incomplete test jobs
  * ci: backend: lava: change option to handle lava boot results
* core:
  * core: `Build.test_suites_by_environment`: make ordering of test results consistent
  * core: admin: mark password field as not required
* misc
  * Add license information for consumption by reuse
  * Added reuse (SPDX compliance tool) to travis.
  * migrate to django2
* doc:
  * doc: ci: add CI_LAVA_HANDLE_BOOT to docs
* plugins:
  * plugins: gerrit: remove `capture_output`
  * plugins: gerrit: set code-review to -1 when tests fail
* Updated translations:
  * Portuguese (Brazil)
  * Polish
  * Norwegian Bokmål

# 0.68.3

* frontend: `results_table`: show "mean (stddev)" details only for metric
  comparison
* core: plugins: fix gerrit plugin

# 0.68.2

* ci: improve parsing of LAVA logs

# 0.68.1

* frontend: fix page title in project settings
* ci: catch YAML ScannerError in LAVA backend

# 0.68

* Translated using Weblate (Portuguese (Brazil))
* test/karma.conf.js: make chromium work on docker
* api: rest: fix rest-framework `detail_route`
* frontend
  * frontend: js: update lodash to 4.17.14
  * frontend: compare-tests: fix auto complete initialization
  * frontend: compare-tests: add auto-width to select2
  * frontend: css: fix word-wrap
* core:
  * core: add management sub-command to create/update auth tokens
  * core: api: support passing test log in the JSON file
  * core: plugins: fix builtin plugins path
  * core: plugins: add gerrit builtin plugin
* ci
  * ci: lava: fetch test logs if available
  * ci/backends/lava: modify unit tests to check logs retrieval
* docs: document notification plugins

# 0.67

* frontend:
  * frontend: combine compare menu
  * frontend: add compare build to build list
  * frontend: order projects alphanumerically
  * frontend: rename "Explore" menu to "Groups"
  * frontend: metrics: display range of values
  * frontend: metrics: fix Y axis configuration
  * frontend: add option to compare build and projects by metrics
  * frontend: bring compare menu to front
  * frontend: use gettext in login template
  * javascript: changed floatThread to floatThead
* ci:
  * ci: backend: lava: extract settings to separate method
  * ci: backend: lava: add option to ignore lava boot results
* doc:
  * doc: ci: add `CI_LAVA_IGNORE_BOOT` to docs
* core
  * core: queries: make data entries more readable
  * core: queries: expose measurement ranges
  * core: add MetricComparison class
* scripts/testdata: generate more interesting metrics
* i18n:
  * New translation: Spanish (Mexico)
  * Updated translation: Norwegian Bokmål
  * Updated translation: Polish
  * Updated translation: Portuguese (Brazil)

# 0.66

* frontend
  * frontend/templatetags: fix pagination get_page_url
  * frontend: fix floatThead
  * charts: always redraw dynamic metrics
* api:
  * api: allow Authorization: Token in resubmit calls
  * api: return proper value when resubmit is not successful
* core:
  * metrics: Add dynamic metric summary
* i18n
  * Added a partial Norwegian Bokmål translation
  * Updated Brazilian Portuguese translation
  * doc/translating.rst: add instructions to translate on weblate

# 0.65

* i18n: add Brazilian portuguese translation for SQUAD UI
* core
  * core: `import_data`: adjust dates on imported data
  * core: `import_data`: ignore test runs with no metadata
  * core: `import_data`: display some indication of progress
  * Add environment to MetricsSummary and TestSummary
  * Add BuildSummary class
* doc:
  * doc/api: fix HTTP method for resubmit endpoints
  * doc: add details about LAVA multinode jobs
* api:
  * api: fix authentication in resubmit API
  * api: fix tests for CI API
* ci:
  * ci: allow cloning LAVA results with measurements
  * ci: add support for LAVA multinode jobs
  * ci: make sure null backend is never used
* frontend
  * Add metrics summary to charts
  * Make default charts to be overall metrics summary per build

# 0.64.1

* i18n: ship compiled message catalogs

# 0.64

* frontend:
  * rewrite build settings with Django forms/views
  * Standardize "settings" tab to be similar to Group and Project settings tab name
  * extract "test results summary" into a shared template
  * mark strings for translation
  * Show "Projects" tab only if user had specific permission
  * compare_projects.jinja2: add pagination to test results
  * cache downloaded static assets
  * frontend/project_settingspy: add more attributes
  * squad/controllers/charts.js: display tooltip on line hover
  * frontend: allow empty searches in test comparison page
* i18n
  * Document translation process
  * scripts/update-translation-files: drop empty line at the end of .pot files
  * add Polish translation for SQUAD UI
* core: mark strings for translation
  * core/notification.py: add number of skipped tests to default email template subject
  * core/notification.py: include metrics in context of email notifications
* ci: testfetch: add option to fetch in the background
* api
  * api: add subscribe/unsubscribe endpoints to Project
  * api/rest: Add KnonwIssue filtering to Test object
  * doc: added description for subscribe/unsubscribe endpoints
* doc/index.rst: add missing dependency on Debain/Ubuntu
* fix yaml.load default Loader warning

# 0.63

* api:
  * Fix api/data call date arguments
  * avoid crash on delayed reports with empty error message
  * fix serialization of `Project.enabled_plugins_list`
* ci:
  * lava: compose boot test identifier from `job_name`, i.e. instead of just
    "boot", the boot tests results from lava will be named
    "boot-${device-type}"
* core:
  * add 'users' management command
  * group membership is now represented explicitly, and there are three access levels:
    * result submitters (can submit test results)
    * admins (can change anything in the project)
  * drop obsolete Token model
  * Add support for archiving projects (Archived projects are hidden by default
    from from the group page)
* docker: reduce image size
* frontend:
  * Add build settings tab
  * Add group and project self service interfaces. it is now possible for
    regular users to:
    - Create new groups (authenticated users only)
    - Create users namespaces (groups in the format "~${username}"), to host
      personal projects
    - On groups where one is an admin:
      - Edit group setttings
      - Delete the group
      - Create new projects
    - On projects where one is a admin:
      - Edit project settings
      - Delete the project
  * mark strings that compose the home page as translatable
* i18n: add initial infrastructure
* mail: add bulk mail headers to outgoing mail to avoid autoreplied

# 0.62.1

This release has no functional changes. It just fixes the artifacts published
for the previous release.

# 0.62

* core:
  * models.EmailTemplate: add jinja2 syntax validation
  * TestComparison: avoid loading too many objects at once.
    This fixes a long-running issue with excess RAM usage on workers.
  * allow superuser access to all groups, as well as access to empty groups by
    group members.
  * Refactor project status rebuild command
* frontend:
  * add pagination to builds view
  * support groups and project with empty name
  * prevent displaying 'secrets' from LAVA job definition
  * make regressions and fixes popover stay on screen until explicitly closed,
    so the data in them can be copied for pasting elsewhere.
* docker
  * docker-compose.yaml: add initial version
* celery:
  * set maximum number of producer connection attempts
* api:
  * Add query result limit to api/data

# 0.61

* Add management command to update project statues from scratch.
* travis:
  * fix detection of Javascript test failures
  * fix capture of exit status
* Fix a few javascripting
* config.js: removed 'content-type' configuration
* Add import to appConfig for compare.js
* Fix broken charts tests
* Refactor ng apps
* squad/_threshold_table.jinja2: restrict admin controls
* squad/_threshold_table.jinja2: give more specific restriction
* Make all ajax requests contain CSRF header
* Refactor angular apps
* Initialize charts with default summary on all environments.
* Error output missing from failed test cases in tests view.
* api: add missing fields to ProjectStatusSerializer
* core/notification.py: turn off escaping for text emails
* docs: add step-by-step on how to set up SQUAD with LAVA
* Fix previous build ordering in project status test comparison.

# 0.60

* Make notification strategy a per-recipient choice.
* api:
  * fix URL generated to baseline in DelayedReport
  * fix report caching
  * add 'subject' to reports
*  frontend: turn Thresholds metrics name into a select control.

# 0.59

* Add community connector files for Google Data Studio data source.
* doc: correct errata in curl example
* api:
  * restrict visibility of groups via the API
  * Add all test results filtering.
* ci:
  * ci/backend/lava.py: fallback `project_settings`

# 0.58 (0.57)

* api:
  * fix the /builds/<id>/report API

# 0.56

* api:
  * add schema for REST API clients.
  * make api/data returns all results if the metrics is not specified.
  * add endpoint for delayed reports, which are produced in the background
* ci
  * lava: add option to handle lava suite
  * ensure that CI test jobs are always explicitly linked to a target Build
    object.
* core:
  * Always create a ProjectStatus instance together with a Build one. This
    solves a long-standing issue where builds that did not receive any test
    results yet do not show up in the UI.
* core, frontend:
  * add support specifying metric thresholds.
  * add support for marking points as outliers.
  * squad.core.data: fix result checking
* frontend:
  * limit filtering on build page to suite names

# 0.55

* frontend:
  * fix handling of custom templates for 404 and 401 reponses
  * Merge angular apps on build page into one.
* core, frontend: implement data retention policy
* celery: log memory usage for tasks that use more than 1MB
* ci:
  * fix testjobs resubmit
* api:
  * gracefully handle incorrect project IDs in filters
  * fix test comparison results

# 0.54

* frontend:
  * Add Annotation line in graphs.
  * Add tooltips on chart sliders.
  * Add Unit tests for JS code.
* ci:
  * lava: Clean up `is_pipeline` checks.
* core:
  * add tracking to EmailTemplate changes

# 0.53.1

* frontend: Fix missing changes in Jinja templates

# 0.53

* frontend: migrate all templates to Jinja2
* core:
  * fix incorrect notification template names
  * comparison: compose results from a single database lookup

# 0.52.1

* Backport fixes from master branch:
  * frontend: fix pagination iterator variable
  * celery: really set celery to log with the same settings as the main app
  * celery: workaround missing attribute in billiard frame objects

# 0.52

* Add infrastructure for counting database queries
* squad.manage: check performance counts when running tests
* api:
  * add advanced filtering backend
  * add suitemetadata endpoint
  * add support for listing suite/test names in project
  * `test.api.test_rest`: add extra test data
* core: TestComparison: optimize database access
* frontend:
  * Add indicator when adding/updating tests.
  * fixes to compare.js and compare.html
  * fix test history table for Chrome
  * Fix `test_run`'s `job_id` on build page
  * limit testjob/<id> urls to support only integers
  * replace comparetest combos with select2
  * Move chart.js bundle script from base template to metrics.
  * charts: Remove x-axis ticks in case of an empty result set.

# 0.51.2

* core: NotificationDelivery: allow new notifications on changes
* core: TestComparison: fix performance regression handling xfail

# 0.51.1

* scripts/release: don't distribute `local_settings.py`

The previous release erroneously included a local configuration file, and has
been removed from PyPI. This release fixes that mistake, and supercedes the
previous.

# 0.51

* core:
  * Make order of tests important in notifications
  * notifications: avoid duplicated "X FAILED TEST JOBS" notifications
  * queries: use build date for X axis
  * queries: also count xfail when calculating test pass %
  * queries: fix Test pass % in the presence of multiple test runs
  * TestComparison: record xfail -> pass transitions as fixes
* frontend:
  * build page: visually indicate that "more info" is available
  * improve presentation of known issues in the UI
  * display reason for build being unfinished
  * create separate view for full metadata
  * Make it possible to display the charts page in fullscreen
  * test history: add links to group and project
* api:
  * allow to filter ProjectStatus by `last_updated` field
  * add 'comparetest' to the api UI header
  * provide metrics data in CSV as well
  * Limit number of points in charts
  * fix pagination in TestRun detail routes

# 0.50.1

* frontend:
  * display "Not submitted and" "Not fetched" is list of test jobs
* core:
  * admin: List test counts for ProjectStatus
  * add 'xfail' to default test statuses
* ci:
  * lava: avoid extra request when fetching results

# 0.50

* api:
  * add regressions and fixes to ProjectStatus
  * add test for api/knownissues/ endpoint
  * allow for filtering with substrings
  * change pagination for some views
  * fix KnownIssuesViewSet filter fields
  * fix TestJobFilter to allow TestRun relation
  * speed up API UI for builds
* core:
  * add counter for tests with status xfail
  * cache `Status.has_metrics`
  * notification: avoid duplicate notifications
  * notification: ensure metadata is sorted
  * ProjectStatus: make test count fields default to 0
  * rename KnownIssue.environment to `environments`
  * tasks/RecordTestRunStatus: reduce code duplication
  * Test: record xfail when matching any active known issue
* doc: added docs on REST API
* frontend:
  * add indication of unfinished builds
  * allow substring searches in compare test view
  * allow users to subscribe/unsubscribe to email notifications in a project
  * build: improve column widths in test results table
  * build: make "details" URL parameter independent of selection order
  * build page: also expand details when clicking suite name
  * display known issues across the UI
  * download: handle packages without a top-level directory
  * fix 500 when accessing nonexisting build testjobs
  * fix links to test run details
  * fix `test_run.html` after changes to templatetags
  * present regressions and fixes in the build list
  * redesign build page for speed
  * `test_run`: remove `<small>` from UI
  * add tests to cover all basic URLs

# 0.49

* frontend:
  * add shortcut to latest finished build
  * add compare test page with dynamic content
* api:
  * allow for baseline selection with build/<id>/email API
  * add Suite endpoint
  * make API web frontend more responsive
  * add pagination to `test_result` route
  * add `full_name` to project
* ci:
  * admin: list testjob creation timestamp
  * make sure test job is marked fetched
* core:
  * Build: check expected test runs even with CI jobs

# 0.48

* frontend:
  * improve footer wording
  * Group testresults by suite and env in build page
* api:
  * add Test object and more filtering options
* core:
  * ProjectStatus: cache test run counts. This provides a large speedup to the
    project page.
* ci:
  * lava: fix case when LAVA fails to provide `error_type`

# 0.47

* core:
  * ProjectStatus: correctly handle 0 `expected_test_runs`
  * detect changes from 'fail' to 'pass'
* frontend:
  * add SVG badge as separate view
* api:
  * add endpoint for PatchSource object
  * make all 'id' fields read-only
  * expose 'finished' flag to Build
* ci:
  * lava: prevent password leaking in error messages
* scripts:
  * add squad-config script for managing external config

# 0.46.2

This release provides the proper artifacts for SQUAD 0.46

# 0.46.1

The release artifacts for this version are incorrect, and should not be used.

# 0.46

The release artifacts for this version are incorrect, and should not be used.

* api:
  * fix crash when accessing TestRun.Metrics
  * add endpoint for KnownIssue object
  * order build results by ascending instead of descending
* ci/Backend: allow disabling polls
* ci/admin: show poll_interval and max_fetch_attempts in Backend listing
* core:
  * add tests for KnownIssues
  * display known issues in email notifications
  * limit Project.enabled_plugins_list to applicable plugins
  * limit PatchSource.implementation to related plugins
  * Add KnownIssue model class
* frontend:
  * Improve TestRun and TestSuite pages
  * remove 'Build' and 'Test Run' from the page header
  * display when known issue is intermittent
  * display known issues in light orange
  * test history: display known issues
  * display Known issues in test results page
  * build page: sort test runs by suite slug
* plugins:
  * add Github build status notification plugin
  * add optional `features` option to plugin fields
  * add get_plugins_by_feature
  * split core plugin support from builtin plugins

# 0.45.1

* ci/admin: only link to test job with valid URL
* settings: fix periodic tasks schedule

# 0.45

* api:
  * add endpoint for creating builds
  * report issues with email templates without crashing
* ci/lava:
  * allow resubmitting LAVA Test failures
* core:
  * add base infrastructure for patch builds
  * add CreateBuild task
  * add tasks to notify patch builds
  * change Project.enabled_plugins_list to PluginListField
* plugins:
  * add API for patch source notifications
  * add PluginListField and PluginField
* frontend:
  * improve the readabiliy of the headers
  * switch tabs to pills so they are easier to locate visually
  * handle missing suite names in test history page
  * link to test run from build page (insted of to details of each suite)

# 0.44

* api:
  * disable HTML controls for filtering
  * only expose Build.metadata on specialized endpoint
  * testjobs: prefetch backend objects
* core:
  * prevent fetching large text fields from TestRun by default
  * TestHistory: allow pinning the top build
  * TestHistory: sort environments by slug
* frontend: test history: add permalink with pinned top build

# 0.43

* Drop Django 1.10 support
* core:
  * add pagination support to TestHistory
* api:
  * minor fixes to make API more uniform
  * omit Build.finished
  * prefetch test runs when handling builds
* frontend:
  * paginate test history page
  * get user avatars from gravatar.com
  * add TestJob count numbers to build view
* ci:
  * admin: display TestJob submission date
* squad.run:
  * display unicorn options
  * add --fast option for fast startup

# 0.42

* core:
  * Mark optional fields optional
  * fetch project and group for Test
  * add DB indices for identifier-like fields
  * comparison: avoid extra, slow database query

# 0.41

* api:
  * allow write-only access to backend tokens
  * add 'email' method to the Build object
  * added tests for build/email REST api
  * add Group and UserGroup objects to REST api
  * add tests for Group REST API
  * allow changing slug in UserGroups
  * add 'id' and 'metadata' fields to Build object
  * add all Project fields to REST API
  * allow filtering on most of the Project fields
  * add search and sorting features
* ci:
  * add reference to resubmitted TestJob
  * make `parent_job` read-only in admin
  * lava: allow supressing resubmit emails with backend settings
* core: add Group.description
* frontend:
  * display list of groups in home page
  * add link to TestJob's parent
  * display model.name instead of model.slug
* doc:
  * install.rst: document installation of RabbitMQ
  * restructure docs and include ci setup
* scripts/git-build: allow building package without having runtime dependencies
  installed

# 0.40

* ci:
  * move backend settings to database
* ci/lava:
  * fix resubmit() function
  * properly handle invalid SSH handshake
* core/notification:
  * drop test history info from default templates (eliminates a performance
    bottleneck with builds that have a large number of failed tests)
  * skip creating HTML version of the email if not required
* plugins:
  * add testjob postprocessing hook

# 0.39.3

* celery: correctly load configuration from Django settings

# 0.39.2

* settings: take Celery broker URL via environment

# 0.39.1

* fix crash in admin by removing debug print

# 0.39

* api: add REST API for email templates
* ci/lava:
  * don't crash if there is no metadata
  * update listener to match new LAVA state machine

# 0.38

* core, api: migrate to Django REST Framework tokens
  * The old squad-specific Token model has been migrated to Django REST
    Framework tokens. The actual data for the old tokens is still there, but
    it's not used for anything anymore. It will be automatically removed in the
    next release.
* core:
  * add support for test case variants
* frontend:
  * return 404 on non-existing data
  * add initial user settings UI
  * add API token settings page
  * improve display of descriptions in project list
* api
  * Add CORS support via django-cors-headers
  * fix TestSerializer
  * make Project.slug readonly
* ci/lava:
  * add more strings to automatic resubmit list
  * parse LAVA log using incremental parser
  * add unit test for log parsing

# 0.37

* admin: allow manually triggering post-processing of test run data
* api: add `filter_fields` to BuildViewSet
* api: add ID field to objects returned by REST API
* api: Add ProjectStatus to REST API
* ci: fetch test result data in chunks in LAVA backend
* ci/lava: restore downloading logs
* frontend: Add pagination to test and metric listings
* frontend: fix environment label in tests history table
* frontend: improvements to the resubmit UI
* frontend: paginate "all test results" page
* scripts: add script to migrate testruns between projects
* Store and display metadata about environments, suites, tests, and metrics

# 0.36

* frontend:
  * retitle test results page to "All test results"
  * hide non-failing test results by default
  * improve formatting of "test results" tables
  * link test results to test history in "all test results" page
* ci/lava: don't crash when lava listener provides no status

# 0.35

**Upgrade notes:** this version drops support for starting the celery-related
daemons (worker and scheduler) using the "./manage.py | squad-admin" command
line interface. To start those daemons, you should now use the standard celery
command line interface, i.e.

* `celery -A squad worker` for the worker, and
* `celery -A squad beat` for the scheduler.


**Changes:**

* api:
  * Added a REST API for accessing most of the data in SQUAD. This API is only
    adequate for read-only access for now.
  * The API is self-describing and features a API browser when accessed with a
    web browser. This API browser is linked from the navigation bar at the top.
* frontend:
  * make login link redirect to original page
* settings:
  * respect proxy headers when generating absolute URLs
* upgrade to celery v4
  * Drop support for SQL-backed periodic task scheduling
  * requirements.txt: drop restriction for using celery v3

# 0.34.1

* core/notification: don't spam admins

# 0.34

* ci:
  * add created, submitted and fetched dates to TestJob
  * fill in submission and fetch dates
  * admin: avoid loading all Build and TestRun objects
* core/notification:
  * fix tests for `notification_timeout`
  * core/notification: notify only once on timeout
* frontend:
  * display testjob.failure if available


# 0.33

* squad.run: exec() into an actual gunicorn process
* ci/admin: make Job ID a link to the backend
* ci/lava/listener: log only messages related to test jobs of interest
* ci:
  * save `TestJob.last_fetch_attempt` before fetching
  * delay updating project status until after TestJob is saved
* core
  * tasks: make database transaction explicit
  * make updating project status optional
  * fix failed testjob notification templates

# 0.32.3

* Revert "squad.run: exec an actual gunicorn process"

# 0.32.2

* ci: fix off-by-one error

# 0.32.1

* squad.run: exec an actual gunicorn process
* ci: handle maximum fetch attempts in works as well

# 0.32

* core: fix query for "test pass %"
* ci: limit fetch attempts with temporary issues
* ci/lava:
  * Fix exception handling for failed log fetching
  * disable log fetching for the moment

# 0.31

* core.admin: list and fiter by ProjectStatus.finished
* ci/lava:
  * speed up parsing of structured logs and test results from YAML
  * fix parsing of test suite names

**IMPORTANT:** starting from this version, the LAVA backend for CI jobs
requires that PyYAML has been compiled with support for libyaml. So if you are
upgrading from a previous version and are using the LAVA integration, make sure
that is the case.

  * `python3 -c 'import yaml; print(yaml.__with_libyaml__)'` must print `True`
  * if not, make sure you have the development files for libyaml installed
    (e.g. `libyaml-dev`) _before_ (re)installing PyYAML.
    * To reinstall PyYAML:
      `pip install --upgrade --force-reinstall --no-cache-dir PyYAML`

# 0.30.1

* ci: Reimplement poll as a series of fetch operations
* core.queries: optimize query for "tests pass %" metric
* frontend: add links to test history

# 0.30

* ci:
  * formally associate TestJobs with their target build
  * lava: remove per-job failure notifications
* core/Build: use pending CI jobs in the definition of `finished`
* core/notification:
  * add support for delayed notifications
* core/notification:
  * drop retry logic from notification task
  * extract a reusable base HTML template
  * force sending notifications after a timeout
  * improve design of moderation warning in HTML
  * notify admins of failed test jobs
* frontend:
  * add filtering to build page
  * add floating table headers
  * list failures on top, and allow filtering in Test results page
  * prioritize test suites with failures in build page

# 0.29.1

* frontend: return 404 for unexisting build on test run page
* core:
  * allow empty list of enabled plugins
  * notifications: add missing important metadata dict

# 0.29

* api: set 'submitted=True' on TestJobs created with 'watchjob' API
* ci:
  * add more details to failed test job notifications
  * lava: delay email notification to allow for storing the object
  * lava: update TestJob name and status
  * update failed testjob subject
* core:
  * notification: include only important metadata in emails
  * postprocess test runs, using plugins
  * Project: add field to store list of enabled plugins
* frontend
  * hide group slug when in the group page
  * Fix loading metrics chart configuration from URL
* plugins:
  * add the beginnings of a plugin system
  * add basic documentation for both using and writing plugins
  * add a `linux_log_parser` plugin as an example. It still needs a few
    improvements before it can start to be used seriously.

# 0.28

* core:
  * modify `test_suites_by_environment` to provide count of pass, fail, and
    skip tests
* README.rst: fix copyright notice to mention AGPL
* frontend:
  * optimize build listings
  * return 404 on non-existing Build, TestRun, and Attachment
  * re-add missing red background for failed tests in test results tables
* doc: move documentation to sphinx

# 0.27

* core:
  * display metadata in a grid in HTML notifications emails
  * handle list as metadata keys in emails
  * Test: add `log` field
* frontend:
  * add line break between metadata list values
  * highlight rows under the mouse on project and build listings, and in the
    list of test suites in the build page
  * remove "ed" suffix from test results
  * align width of top navigation bar with content width
  * turn entire suite rows into links
  * improve HTML markup
  * redesign the TestRun page
    * failures are listed at the top, with their corresponding log snippet if
      available
      * note however that assigning log snippets to test results is not
        implemented yet; will probably be available on the next update.
    * skipped and passed tests are hidden by default, but can be displayed with
      a click

# 0.26

* Dockerfile: run out of the box
* api: create Build object when creating TestJob
* core, ci: drop usage of VersionField
* core:
  * don't overwrite ProjectStatus with earlier data
  * fix test for not sending duplicated notifications
  * remove ProjectStatus creation/update from transaction
  * make it possible to specify important metadata
  * make Build metadata the union of test runs metadata
* ci: make TestJob.build the same type as Build.version
* frontend:
  * add missing "incomplete" word in builds table
  * add titles for project internal pages
  * present test jobs in build page
  * convert builds table into a grid
  * redesign the build page
  * update Font Awesome hash
  * use a grid for metadata everywhere
  * display only important metadata for build

# 0.25

* Change license to the Affero GPL, v3 or later
* MANIFEST.in: remove redundant lines
* Normalize email addresses
* README
  * README.rst: remove mention of Debian packages for assets
  * README.rst: update list of dependencies on Debian
* ci: lava: add 'auto-login-action' to automatically resubmitted patterns
* core
  * core/Build: sort test suites in test_suites_by_environment
  * core/notification: Do not send dup notifications
  * core: added project description
* frontend
  * frontend: added support for logging in on small screens
  * frontend: change license mentioned in the header
  * frontend: display skip percentage and tooltips in test bars
  * frontend: download static assets from their original locations
  * frontend: hide project list header on small screens
  * frontend: hide zeros in build listing
  * frontend: improve UI consistency
  * frontend: only replace download.status if needed
  * frontend: use better colors for pass/fail
* gen-test-data: do everything that is needed under the hood
* git-build: fix clean of old builds
* scripts
  * scripts/git-build: build Python packages from the git repository
  * scripts/release: exclude download assets from the `tar vs git` check
  * scripts/travis: abandon git-based cache of static assets
* setup.py: correctly exclude code from test/ from being installed
* submit-test-data: also generate skips

# 0.24

* core
  * provide test suites executed by environment
* README updates

# 0.23

* core/notification:
  * add support for having a custom subject as part of an email notification
    template.

# 0.22

* ci
  * handle fetching failures with less noise, and in a way that is independent
    of the test job backend. This reverts the LAVA-specific handling added in
    0.21.
* ci/lava
  * add support for using boot information from LAVA as an articial boot test
    and as a boot time metric.

# 0.21

* frontend:
  * Add missing red bar in group main page for test failures
* core:
  * add support for per-project custom email templates
  * comparison: use environment name is available
* Add script to run a development environment on docker
* ci/lava
  * log and notify by email any errors when fetching test jobs

# 0.20.3

* core:
  * add management command to force sending an email report.
    * This can be used for example to help local testing
* ci/lava:
  * filter events down do the ones we can (and want to) handle
* frontend:
  * fix crash when viewing projects with no data

# 0.20.2

* frontend:
  * fix javascript error

# 0.20.1

* core:
  * fix update of ProjectStatus objects

# 0.20

* core:
  * admin:
    * move "re-send notification" action to ProjectStatus
    * expose Build data
    * sort ProjectStatus by build date
  * Test results:
    * use just "skip" instead of "skip/unknown"
  * ProjectStatus: determine `previous` (baseline for comparison in
    notification) dinamically, by getting the previous build that has complete
    data.
  * Project: avoid duplicated projects in listing
  * notification: list explicitly number of skipped tests
* frontend: improve wording on project home page
* ci/listen: spawn listener processes without fork()

# 0.19

* core:
  * notifications:
    * retry if ProjectStatus id does not exist (yet). Handles race condition
      when worker process tries to send a notification before the corresponding
      data has been commited to the database by the process requesting the
      notification.
  * Build data:
    * don't count tests that have been retried twice. e.g. if a test job is
      resubmitted, the test results produced will override any corresponding
      test results from previous test jobs.
* frontend:
  * optimize database queries used to compose build page. Data tested shows a
    reduction of ~95% in the response time.
  * avoid producing exceptions when users try to access an unexisting group
    (not just returns an 404 error quietly).
  * show all builds in the project front page (i.e. don't omit the last build,
    that already has details displayed, from the full list of builds).
  * hide resubmit button from unprivileged users (who should't be allowed to
    resubmit in the first place).
* ci/lava:
  * automatically resubmit jobs that failed due to infrastructure problems that
    we already know about.

# 0.18.1

* core/admin:
  * display "moderate notifications" in project listing
  * filter ProjectStatus by project
  * add several filters for the project listing
* settings: set `SERVER_EMAIL`

# 0.18

* ci:
  * mark proper TestRun status on awkward LAVA failure
* frontend:
  * display squad version in the base template
  * several improvements to the UI to make browsing data more effective
* core:
  * notitifications are now sent immeditately after there is enough data for
    each build, instead of on pre-scheduled times.
  * notifications can now be moderated by admins before being sent out to
    users.

# 0.17

* core:
  * update "last updated" data every time new results arrive for a given build
  * notification: clearly identify tests that never passed as such
* ci:
  * lava: report incomplete TestRun when TestJob is canceled
* frontend:
  * fix group page to use correct status data (pass/fail counts, metric summary)

# 0.15

* core:
  * Test names are now ordered alphabetically by default
  * Site home page and project home page were fixed to display the correct build
    status information (tests pass % and metric summary)
  * notification: avoid spurious empty lines in plain text notification
  * admin: allow filling in slug when creating Environment
  * notification: group columns by environment in changes table
  * notification: send a single email
  * record project status at submission time instead of only when processing
    notifications
  * notification: add a per-project flag to control whethet to send a text/html
    alternative representation together with plain text content
* ci:
  * add job\_url to TestRun metadata if present
* ci/lava
  * filter LAVA logs to include only the serial console output
* infrastructure
  * settings: enable exception notifications by email
* frontend:
  * fix resubmit JS code
  * serve TestRun logs directly (i.e. allow viewing them in browser instead of
    forcing a download)
