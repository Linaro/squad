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
