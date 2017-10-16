web: ./manage.py runserver
worker: ./manage.py celery worker --loglevel INFO
scheduler: ./manage.py celery beat --pidfile=''
listener: ./manage.py listen
