FROM debian:buster

RUN apt-get update && \
    apt-get install -qy auto-apt-proxy && \
    apt-get install -qy \
        python3 \
        python3-celery \
        python3-coreapi  \
        python3-django \
        python3-django-cors-headers \
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

RUN ln -sfT container_settings.py /app/squad/local_settings.py

# downloads if needed and prepares static assets
RUN python3 -m squad.frontend
RUN ./manage.py collectstatic --noinput --verbosity 0
RUN cd /app && python3 setup.py develop

RUN useradd --create-home squad
RUN mkdir -m 0755 /app/tmp && chown squad:squad /app/tmp
USER squad
ENV SQUAD_STATIC_DIR /app/static
ENV ENV production
