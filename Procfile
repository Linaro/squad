web: ./manage.py runserver
worker: ./manage.py celery worker --loglevel INFO
scheduler: ./manage.py celery beat --loglevel WARN --pidfile=''
listener: ./manage.py listen
