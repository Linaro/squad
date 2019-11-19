FROM debian:buster-slim

RUN apt-get update -q=2 && \
    apt-get install -q=2 --no-install-recommends iproute2 auto-apt-proxy && \
    apt-get install -q=2 --no-install-recommends \
        gettext \
        python3 \
        python3-celery \
        python3-coreapi  \
        python3-django \
        python3-django-cors-headers \
        python3-django-crispy-forms \
        python3-django-simple-history \
        python3-django-filters \
        python3-djangorestframework \
        python3-djangorestframework-filters \
        python3-gunicorn \
        python3-jinja2 \
        python3-markdown \
        python3-msgpack \
        python3-psycopg2 \
        python3-dateutil \
        python3-yaml \
        python3-zmq \
        python3-requests \
        python3-sqlparse \
        python3-svgwrite \
        python3-whitenoise \
        wget \
        unzip

WORKDIR /app
COPY . ./

RUN ln -sfT container_settings.py /app/squad/local_settings.py && \
    python3 -m squad.frontend && \
    ./manage.py collectstatic --noinput --verbosity 0 && \
    ./manage.py compilemessages && \
    REQ_IGNORE_VERSIONS=1 python3 setup.py develop --no-deps && \
    useradd --create-home squad && \
    mkdir -m 0755 /app/tmp && chown squad:squad /app/tmp

USER squad
ENV SQUAD_STATIC_DIR /app/static
ENV ENV production
