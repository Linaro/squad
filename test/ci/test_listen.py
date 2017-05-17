from django.test import TestCase
from mock import patch, MagicMock, call


from squad.ci.models import Backend
from squad.ci.management.commands.listen import ListenerManager, Command


class TestListenerManager(TestCase):

    @patch('squad.ci.management.commands.listen.Listener')
    def test_start(self, Listener):
        backend = Backend.objects.create(name="foo")
        manager = ListenerManager()

        manager.start(backend)

        Listener.assert_called_with(backend)
        instance = Listener.return_value
        instance.start.assert_called_once()

    @patch('squad.ci.management.commands.listen.Listener')
    def test_stop(self, Listener):
        backend = Backend.objects.create(name="foo")
        manager = ListenerManager()

        manager.start(backend)
        manager.stop(backend.id)

        Listener.return_value.terminate.assert_called_once()

    @patch('squad.ci.management.commands.listen.Listener')
    def test_cleanup(self, Listener):
        backend1 = Backend.objects.create(name="foo")
        backend2 = Backend.objects.create(name="bar")
        manager = ListenerManager()
        manager.start(backend1)
        manager.start(backend2)

        manager.stop = MagicMock()

        manager.cleanup()

        manager.stop.assert_has_calls([call(backend1.id), call(backend2.id)], any_order=True)

    @patch('squad.ci.management.commands.listen.Listener')
    def test_keep_listeners_running_added(self, Listener):
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
        manager.start.assert_called_with(backend2)

        manager.stop.assert_not_called()

    @patch('squad.ci.management.commands.listen.Listener')
    def test_keep_listeners_running_removed(self, Listener):
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

    @patch('squad.ci.management.commands.listen.Listener')
    def test_keep_listeners_running_changed(self, Listener):
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


class TestCommand(TestCase):

    @patch("squad.ci.management.commands.listen.ListenerManager")
    def test_handle(self, ListenerManager):
        command = Command()
        command.handle()

        ListenerManager.assert_called_once()
        ListenerManager.return_value.run.assert_called_once()
