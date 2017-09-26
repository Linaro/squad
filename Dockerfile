FROM debian:stretch
RUN apt-get update && \
  apt-get install -qy auto-apt-proxy && \
  apt-get install -qy \
    python3-dateutil \
    python3-django \
    python3-celery \
    python3-django-celery \
    python3-jinja2 \
    python3-whitenoise \
    python3-zmq \
    wget \
    unzip \
    gunicorn3

WORKDIR /app
COPY . ./

# downloads if needed and prepares static assets
RUN python3 -m squad.frontend
RUN ./manage.py collectstatic --noinput --verbosity 0

RUN useradd --create-home squad
USER squad
ENV SQUAD_STATIC_DIR /app/static
ENV ENV production
CMD sh -c "./manage.py migrate && exec gunicorn3 squad.wsgi --bind 0.0.0.0:${PORT:-8000}"
