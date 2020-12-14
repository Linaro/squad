FROM debian:buster-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -q=2 && \
    apt-get install -q=2 --no-install-recommends iproute2 auto-apt-proxy && \
    apt-get install -q=2 --no-install-recommends \
        python3 \
        python3-celery \
        python3-coreapi  \
        python3-cryptography \
        python3-dateutil \
        python3-dev \
        python3-django \
        python3-django-auth-ldap \
        python3-django-cors-headers \
        python3-django-celery-results \
        python3-django-crispy-forms \
        python3-django-filters \
        python3-django-simple-history \
        python3-djangorestframework \
        python3-djangorestframework-filters \
        python3-djangorestframework-extensions \
        python3-future \
        python3-gunicorn \
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
        tmux \
        openssh-client

# Prepare the environment
COPY . /squad-build/

ENV SQUAD_STATIC_DIR=/app/static

RUN cd /squad-build && ./scripts/git-build && \
    pip3 install --no-dependencies \
        ./dist/squad*.whl \
        squad-linaro-plugins \
        sentry-sdk==0.14.3 \
        zipp \
        importlib-metadata==3.1.1 \
        asgiref \
        django-bootstrap3 \
        django-storages==1.9 && \
    pip3 install boto3==1.15 && \
    cd / && rm -rf /squad-build && \
    mkdir -p /app/static && \
    useradd -d /app squad && \
    python3 -m squad.frontend && \
    squad-admin collectstatic --noinput --verbosity 0 && \
    squad-admin compilemessages && \
    chown -R squad:squad /app

# TODO: use --ignore for `squad-admin compilemessages` to save time compiling
# messages from all installed packages: https://docs.djangoproject.com/en/3.0/ref/django-admin/#cmdoption-compilemessages-ignore

USER squad
