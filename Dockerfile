FROM debian:bullseye-backports

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -q=2 && \
    apt-get -qq install --no-install-recommends iproute2 auto-apt-proxy >/dev/null && \
    apt-get -qq install --no-install-recommends >/dev/null \
        python3 \
        python3-aiohttp \
        python3-asgiref \
        python3-celery \
        python3-coreapi  \
        python3-cryptography \
        python3-dateutil \
        python3-dev \
        python3-future \
        python3-gunicorn \
        python3-importlib-metadata \
        python3-jinja2 \
        python3-markdown \
        python3-msgpack \
        python3-pip \
        python3-psycopg2 \
        python3-requests \
        python3-setuptools \
        python3-sqlparse \
        python3-svgwrite \
        python3-wheel \
        python3-whitenoise \
        python3-yaml \
        python3-zipp \
        python3-zmq \
        fail2ban \
        gettext \
        git \
        libdbd-pg-perl \
        libldap2-dev \
        libpq-dev \
        libyaml-dev \
        moreutils \
        postgresql-client \
        unzip \
        wget \
        openssh-client && \
    apt-get -qq -t bullseye-backports install --no-install-recommends >/dev/null \
        python3-django \
        python3-django-auth-ldap \
        python3-django-celery-results \
        python3-django-crispy-forms \
        python3-django-debug-toolbar \
        python3-django-filters \
        python3-djangorestframework \
        python3-djangorestframework-filters && \
    pip3 install --no-dependencies \
        "amqp>=5.0.5" \
        squad-linaro-plugins \
        sentry-sdk==0.14.3 \
        "django-simple-history>3.0" \
        django-bootstrap3 \
        django-cors-headers \
        drf-extensions \
        django-allauth==0.46.0 \
        django-simple-history==3.1.1 \
        django-health-check==3.16.4 && \
    pip3 install boto3==1.15 django-storages[google]==1.13.2

# Prepare the environment
COPY . /squad-build/

ENV SQUAD_STATIC_DIR=/app/static

RUN cd /squad-build && ./scripts/git-build && \
    pip3 install --no-dependencies ./dist/squad*.whl && \
    cd / && rm -rf /squad-build && apt-get remove -y git && apt-get autoremove -y && \
    mkdir -p /app/static && \
    useradd -d /app squad && \
    python3 -m squad.frontend && \
    squad-admin collectstatic --noinput --verbosity 0 && \
    chown -R squad:squad /app && \
    cd /app

USER squad
