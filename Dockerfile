FROM debian:buster-backports

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
        openssh-client && \
    apt-get -t buster-backports install -q=2 --no-install-recommends \
        python3-django \
        python3-django-auth-ldap \
        python3-django-cors-headers \
        python3-django-celery-results \
        python3-django-crispy-forms \
        python3-django-simple-history \
        python3-djangorestframework \
        python3-djangorestframework-extensions && \
    pip3 install --no-dependencies \
        squad-linaro-plugins \
        sentry-sdk==0.14.3 \
        zipp \
        importlib-metadata==3.1.1 \
        asgiref \
        django-bootstrap3 \
        django-filter==2.0.0 \
        djangorestframework-filters==1.0.0.dev0 \
        django-storages==1.9.1 \
        django-allauth==0.44.0 \
        django-health-check==3.16.4 && \
    pip3 install boto3==1.15

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
    cd `python3 -c 'import squad; print(squad.__path__[0])'` && squad-admin compilemessages && \
    cd /app

USER squad
