FROM debian:stretch
RUN apt-get update && \
  apt-get install -qy auto-apt-proxy && \
  apt-get install -qy \
    python3-dateutil \
    python3-django \
    python3-celery \
    python3-django-celery \
    python3-whitenoise \
    python3-pip \
    fonts-font-awesome \
    libjs-angularjs \
    libjs-bootstrap \
    libjs-lodash \
    gunicorn3

WORKDIR /app
COPY . ./

# debug
RUN find
RUN env

# creates symlinks to packaged static assets
RUN python3 -m squad.frontend
RUN ./manage.py collectstatic --noinput

RUN chown -R www-data /app
EXPOSE 8000

USER www-data
CMD sh -c "./manage.py migrate && exec gunicorn3 squad.wsgi --bind 0.0.0.0:${PORT:-8000}"
