Development-related notes
=========================

Checklist for loading a copy of a production database
-----------------------------------------------------

on the server:

* dump the database: squad-admin dumpdata -o /tmp/data.json auth core ci
* compress the dump: gzip /tmp/data.json

locally:

* copy dump:         scp SERVER:/tmp/data.json.gz /tmp/
* decompress dump:   gunzip /tmp/data.json.gz
* load dump:         ./manage.py loaddata /tmp/data.json
* create superuser:  ./manage.py createsuperuser
* anonymize data:    ./manage.py prepdump # avoid mailing users
