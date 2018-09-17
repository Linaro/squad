FROM debian:stretch
RUN apt-get update && \
  apt-get install -qy auto-apt-proxy && \
  apt-get install -qy python3 \
    python3-pip \
    libpq-dev \
    libyaml-dev \
    wget \
    unzip

COPY requirements.txt /srv/
RUN pip3 install --no-binary :all: -r /srv/requirements.txt

WORKDIR /app
COPY . ./

# downloads if needed and prepares static assets
RUN python3 -m squad.frontend
RUN ./manage.py collectstatic --noinput --verbosity 0

RUN useradd --create-home squad
USER squad
ENV SQUAD_STATIC_DIR /app/static
ENV ENV production
CMD sh -c "./manage.py migrate && exec gunicorn squad.wsgi --bind 0.0.0.0:${PORT:-8000}"
