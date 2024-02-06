==================================
Quick start: Running SQUAD locally
==================================

SQUAD is a Django application and works just like any other Django
application. If you are new to Django and want to setup a development
environment, you can follow the instructions below. If you want to
install SQUAD for production usage, see :ref:`production_install_ref_label` instead.

Note that SQUAD is Python3-only, so it won't work with Python 2.

Before moving on, there's a system dependency needed for Python to load yaml content
with the C library, install it with::

    apt-get install libyaml-dev

On top of that, the following development packages may be required. Please make
sure they're installed by issuing::

    apt-get install libpq-dev python3-dev build-essential

To install the dependencies::

    pip3 install -r requirements-dev.txt

Alternatively to using pip, on Debian stretch or later you can install
dependencies from the repository::

    apt-get install python3-dateutil python3-django python3-celery \
      python3-django-celery python3-jinja2 python3-whitenoise python3-zmq

To run the tests::

    ./manage.py test

Before running the application, create the database and an admin user
for yourself::

    ./manage.py migrate
    ./manage.py createsuperuser

To run the application locally::

    ./manage.py runserver
