import logging
import signal
import subprocess
import sys
import time
from django.core.management.base import BaseCommand
from django.db.models import Field
from django.db.utils import OperationalError


from squad.ci.models import Backend


logger = logging.getLogger()


class Listener(object):

    def __init__(self, backend):
        self.backend = backend
        self.implementation = backend.get_implementation()

    def run(self):
        backend = self.backend
        impl = self.implementation

        logger.info("Backend %s starting" % backend.name)
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        impl.listen()
        logger.info("Backend %s exited on its own" % backend.name)

    def stop(self, signal, stack_frame):
        logger.info("Backend %s finishing ..." % self.backend.name)
        sys.exit()


class ListenerManager(object):

    def __init__(self):
        self.__processes__ = {}
        self.__fields__ = {}

    def run(self):
        self.setup_signals()
        self.wait_for_setup()
        self.loop()
        self.cleanup()

    def setup_signals(self):
        # make SIGTERM equivalent to SIGINT (e.g. control-c)
        signal.signal(signal.SIGTERM, signal.getsignal(signal.SIGINT))

    def wait_for_setup(self):
        n = 0
        while n < 24:  # wait up to 2 min
            try:
                Backend.objects.count()
                logger.info("listener manager started")
                return
            except OperationalError:
                logger.info("Waiting to database to be up; will retry in 5s ...")
                time.sleep(5)
                n += 1
        logger.error("Timed out waiting for database to be up")
        sys.exit(1)

    def keep_listeners_running(self):
        ids = list(self.__processes__.keys())

        for backend in Backend.objects.all():
            process = self.__processes__.get(backend.id)
            if process:
                # listen disabled; stop
                if not backend.listen_enabled:
                    self.stop(backend.id)
                # already running: restart if needed
                elif fields(backend) != self.__fields__[backend.id]:
                    self.stop(backend.id)
                    self.start(backend)
            else:
                # not running, just start
                if backend.listen_enabled:
                    self.start(backend)
            if backend.id in ids:
                ids.remove(backend.id)

        # remaining backends were removed from the database, stop them
        for backend_id in ids:
            self.stop(backend_id)

    def start(self, backend):
        argv = [sys.executable, '-m', 'squad.manage', 'listen', backend.name]
        listener = subprocess.Popen(argv)
        self.__processes__[backend.id] = listener
        self.__fields__[backend.id] = fields(backend)

    def loop(self):
        try:
            while True:
                self.keep_listeners_running()
                # FIXME: ideally we should have a blocking call here that waits
                # for a change to happen in the database, but we didn't find a
                # simple/portable way of doing that yet. Let's just sleep for a
                # few seconds instead, for now.
                time.sleep(60)
        except KeyboardInterrupt:
            pass  # cleanup() will terminate sub-processes

    def cleanup(self):
        for backend_id in list(self.__processes__.keys()):
            self.stop(backend_id)

    def stop(self, backend_id):
        process = self.__processes__[backend_id]
        if not process.poll():
            process.terminate()
            process.wait()
        self.__processes__.pop(backend_id)


def fields(model):
    return {f.name: getattr(model, f.name) for f in model._meta.get_fields() if isinstance(f, Field)}


class Command(BaseCommand):
    help = """Listens for "live" test results from CI backends"""

    def add_arguments(self, parser):
        parser.add_argument(
            'BACKEND',
            nargs='?',
            type=str,
            help='Backend name to listen to. If ommited, start the master process.',
        )

    def handle(self, *args, **options):
        backend_name = options.get("BACKEND")
        if backend_name:
            backend = Backend.objects.get(name=backend_name)
            Listener(backend).run()
        else:
            ListenerManager().run()
