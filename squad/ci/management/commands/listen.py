import logging
import multiprocessing
import signal
import sys
import time
from django.core.management.base import BaseCommand
from django.db.models import Field


from squad.ci.models import Backend


logger = logging.getLogger()


class Listener(multiprocessing.Process):

    def __init__(self, backend):
        self.backend = backend
        self.implementation = backend.get_implementation()
        super(Listener, self).__init__()

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

    def run(self):
        self.setup_signals()
        self.loop()
        self.cleanup()

    def setup_signals(self):
        # make SIGTERM equivalent to SIGINT (e.g. control-c)
        signal.signal(signal.SIGTERM, signal.getsignal(signal.SIGINT))

    def keep_listeners_running(self):
        ids = list(self.__processes__.keys())

        for backend in Backend.objects.all():
            process = self.__processes__.get(backend.id)
            if process:
                # already running: restart if needed
                if fields(backend) != fields(process.backend):
                    self.stop(backend.id)
                    self.start(backend)
            else:
                # not running, just start
                self.start(backend)
            if backend.id in ids:
                ids.remove(backend.id)

        # remaining backends were removed from the database, stop them
        for backend_id in ids:
            self.stop(backend_id)

    def start(self, backend):
        listener = Listener(backend)
        listener.start()
        self.__processes__[backend.id] = listener

    def loop(self):
        try:
            while True:
                self.keep_listeners_running()
                # FIXME: ideally we should have a blocking call here that waits
                # for a change to happen in the database, but we didn't find a
                # simple/portable way of doing that yet. Let's just sleep for a
                # few seconds instead, for now.
                time.sleep(5)
        except KeyboardInterrupt:
            pass  # cleanup() will terminate sub-processes

    def cleanup(self):
        for backend_id in list(self.__processes__.keys()):
            self.stop(backend_id)

    def stop(self, backend_id):
        process = self.__processes__[backend_id]
        if process.is_alive():
            process.terminate()
            process.join()
        self.__processes__.pop(backend_id)


def fields(model):
    return {f.name: getattr(model, f.name) for f in model._meta.get_fields() if isinstance(f, Field)}


class Command(BaseCommand):
    help = """Listens for "live" test results from CI backends"""

    def handle(self, *args, **options):
        manager = ListenerManager()
        manager.run()
