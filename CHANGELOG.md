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
