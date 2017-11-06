==================================
Development-related notes and tips
==================================

Running a development environment under Docker
----------------------------------------------

To run tests, migrate database, and start the web server::

    ./dev-docker

To open a shell in the development environment::

    ./dev-docker bash


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
