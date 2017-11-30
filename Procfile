web: ./manage.py runserver
worker: celery -A squad worker --loglevel INFO
scheduler: celery -A squad beat --loglevel WARN --pidfile=''
listener: ./manage.py listen
