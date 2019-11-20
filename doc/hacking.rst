==================================
Development-related notes and tips
==================================

Running a development environment under Docker
----------------------------------------------

To run tests, migrate database, and start the web server::

    ./dev-docker

To open a shell in the development environment::

    ./dev-docker bash

**NOTE** if you're running a firewall on your system, like ufw, make sure to
allow the docker interface to interact with your system's. If you're running
ufw, do so with `sudo ufw allow in on docker0`.

Checklist for loading a copy of a production database
-----------------------------------------------------

This procedure assumes you are using PostgreSQL in production, and will use
PostgreSQL locally. If you are using sqlite, then the procedure is trivial
(just copy the database file).


on the server:

* dump the database: pg_dump -F custom -f /tmp/dump squad

locally:

* create empty DB:   createdb squad
* copy dump:         scp SERVER:/tmp/dump /tmp/
* load dump:         pg_restore -d squad -j4 /tmp/dump
* migrate database:  ./manage.py migrate
* create superuser:  ./manage.py createsuperuser
* anonymize data:    ./manage.py prepdump # avoid mailing users


Running Javascript unit tests
-----------------------------

In order to run Javascript unit tests, you need to installl nodejs and npm
package manager, then install the dependencies from the package-lock.json file.
Depending on the distribution, you can either install npm directly from
repositories or alternatevely add PPA and then install it. Here's the
instructions of how to setup up after the npm package manager is installed::

  sudo apt-get install chromium
  npm install

Simply running the Django tests will also run the Javascript unit tests::

  ./manage test

Or, you can run only the Javascript unit tests with one of these commands::

  python3 python3 test/javascript.py  # or
  python3 -m test.javascript
