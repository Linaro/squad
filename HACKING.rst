Development-related notes
=========================

Running a development environment under Docker
----------------------------------------------

To run tests, migrate database, and start the web server::

    ./dev-docker

To open a shell in the development environment::

    ./dev-docker bash


Checklist for loading a copy of a production database
-----------------------------------------------------

on the server:

* dump the database: squad-admin dumpdata -o /tmp/data.json auth core ci
* compress the dump: gzip /tmp/data.json

locally:

* backup local DB:   mv db.sqlite3 db.sqlite3.old
* create empty DB:   ./manage.py migrate
* copy dump:         scp SERVER:/tmp/data.json.gz /tmp/
* decompress dump:   gunzip /tmp/data.json.gz
* load dump:         ./manage.py loaddata /tmp/data.json
* create superuser:  ./manage.py createsuperuser
* anonymize data:    ./manage.py prepdump # avoid mailing users
