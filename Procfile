web: gunicorn3 squad.wsgi
worker: python3 -m squad.manage celery worker
scheduler: python3 -m squad.manage celery beat --pidfile=''
listener: python3 -m squad.manage listen
