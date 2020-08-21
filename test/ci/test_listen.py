from django.test import TestCase
from test.mock import patch, MagicMock, call


from squad.ci.models import Backend
from squad.ci.management.commands.listen import ListenerManager, Command
from squad.ci.management.commands.listen import Listener


class TestListenerManager(TestCase):

    @patch('squad.ci.management.commands.listen.subprocess.Popen')
    def test_start(self, Popen):
        backend = Backend.objects.create(name="foo")
        manager = ListenerManager()

        manager.start(backend)

        self.assertEqual(Popen.call_args[0][-1][-1], "foo")

    @patch('squad.ci.management.commands.listen.subprocess.Popen')
    def test_stop(self, Popen):
        backend = Backend.objects.create(name="foo")
        manager = ListenerManager()

        Popen.return_value.poll.return_value = None

        manager.start(backend)
        manager.stop(backend.id)

        Popen.return_value.poll.assert_called_once()
        Popen.return_value.terminate.assert_called_once()
        Popen.return_value.wait.assert_called_once()

    @patch('squad.ci.management.commands.listen.subprocess.Popen')
    def test_cleanup(self, Popen):
        backend1 = Backend.objects.create(name="foo")
        backend2 = Backend.objects.create(name="bar")
        manager = ListenerManager()
        manager.start(backend1)
        manager.start(backend2)

        manager.stop = MagicMock()

        manager.cleanup()

        manager.stop.assert_has_calls([call(backend1.id), call(backend2.id)], any_order=True)

    @patch('squad.ci.management.commands.listen.subprocess.Popen')
    def test_keep_listeners_running_added(self, Popen):
        manager = ListenerManager()
        backend1 = Backend.objects.create(name="foo")

        manager.start = MagicMock()
        manager.stop = MagicMock()

        # start existing backends
        manager.keep_listeners_running()
        manager.start.assert_called_with(backend1)

        # new backend, start it too
        backend2 = Backend.objects.create(name="bar")
        manager.keep_listeners_running()
        manager.start.assert_has_calls([call(backend1), call(backend2)], any_order=True)

        manager.stop.assert_not_called()

    @patch('squad.ci.management.commands.listen.subprocess.Popen')
    def test_keep_listeners_running_removed(self, Popen):
        manager = ListenerManager()
        backend = Backend.objects.create(name="foo")

        manager.stop = MagicMock()

        # start existing backends
        manager.keep_listeners_running()

        # backend is removed
        bid = backend.id
        backend.delete()
        manager.keep_listeners_running()
        manager.stop.assert_called_with(bid)

    @patch('squad.ci.management.commands.listen.subprocess.Popen')
    def test_keep_listeners_running_changed(self, Popen):
        manager = ListenerManager()
        backend = Backend.objects.create(name="foo")

        # start existing backends
        manager.keep_listeners_running()

        manager.stop = MagicMock()
        manager.start = MagicMock()

        # backend is changed
        backend.name = 'bar'
        backend.save()
        manager.keep_listeners_running()

        manager.stop.assert_called_with(backend.id)
        manager.start.assert_called_with(backend)


class TestListener(TestCase):

    def test_run(self):
        backend = MagicMock()
        listener = Listener(backend)
        listener.run()
        backend.get_implementation.return_value.listen.assert_called_once()


class TestCommand(TestCase):

    @patch("squad.ci.management.commands.listen.ListenerManager")
    def test_handle(self, ListenerManager):
        command = Command()
        command.handle()

        ListenerManager.assert_called_once()
        ListenerManager.return_value.run.assert_called_once()

    @patch("squad.ci.management.commands.listen.Backend")
    @patch("squad.ci.management.commands.listen.ListenerManager")
    @patch("squad.ci.management.commands.listen.Listener")
    def test_handle_listener(self, Listener, ListenerManager, Backend):
        backend = object()
        Backend.objects.get.return_value = backend

        command = Command()
        command.handle(BACKEND='foo')

        ListenerManager.assert_not_called()
        Listener.assert_called_with(backend)
        Listener.return_value.run.assert_called()
