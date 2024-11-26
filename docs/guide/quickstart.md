### Quick Start

#### Running SQUAD Locally

SQUAD is a Django application and it is Python3 only. To setup a development environment locally, it can be installed from PyPi using `pip`:

```
$ pip3 install squad
```

To install from repo:

```
$ apt-get install libyaml-dev
```

then

```
$ pip3 install -r requirements-dev.txt
```

Note there is a system dependency that is needed beforehand for Python to load yaml content with the C library.

Alternatively to using pip, on Debian stretch or later you can install dependencies from the repository:

```
$ apt-get install python3-dateutil python3-django python3-celery python3-django-celery python3-jinja2 python3-whitenoise python3-zmq
```

To run the tests:

```
$ ./manage.py test
```

Before running the application, create the database and an admin user for yourself:

```
$ ./manage.py migrate
$ ./manage.py createsuperuser
```

To run the application locally:

```
$ ./manage.py runserver
```
