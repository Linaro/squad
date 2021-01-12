import json


from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from unittest.mock import patch


from squad.core.models import Group, Callback


class CallbackTest(TestCase):

    def setUp(self):
        self.group = Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject', project_settings='{"CALLBACK_HEADERS": {"Authorization": "token 123456"}}')
        self.build = self.project.builds.create(version='mybuild')
        self.event = Callback.events.ON_BUILD_FINISHED

    @patch('requests.post')
    def test_build_callback(self, requests_post):
        url = 'http://callback-target.com'

        callback = self.build.callbacks.create(url=url, event=self.event)
        callback.dispatch()

        self.assertTrue(requests_post.called)
        self.assertTrue(callback.is_sent)

    @patch('requests.post')
    def test_build_callback_with_json_payload(self, requests_post):
        url = 'http://callback-target.com'
        payload = json.dumps({'data': 'value'})

        callback = self.build.callbacks.create(url=url, event=self.event, payload=payload)
        callback.dispatch()

        self.assertTrue(requests_post.called)
        self.assertTrue(callback.is_sent)
        requests_post.assert_called_with(url, json=payload)

    @patch('requests.post')
    def test_build_callback_with_formdata_payload(self, requests_post):
        url = 'http://callback-target.com'
        payload = {'data': 'value'}

        callback = self.build.callbacks.create(url=url, event=self.event, payload=json.dumps(payload), payload_is_json=False)
        callback.dispatch()

        self.assertTrue(requests_post.called)
        self.assertTrue(callback.is_sent)
        requests_post.assert_called_with(url, data=payload)

    @patch('requests.post')
    def test_build_callback_with_auth_headers(self, requests_post):
        url = 'http://callback-target.com'
        headers = {'Authorization': 'token 654321'}

        callback = self.build.callbacks.create(url=url, event=self.event, headers=json.dumps(headers))
        callback.dispatch()

        self.assertTrue(requests_post.called)
        self.assertTrue(callback.is_sent)
        requests_post.assert_called_with(url, headers=headers)

    @patch('requests.post')
    def test_build_multiple_callbacks(self, requests_post):
        url1 = 'http://callback-target1.com'
        url2 = 'http://callback-target2.com'

        self.build.callbacks.create(url=url1, event=self.event)
        self.build.callbacks.create(url=url2, event=self.event)

        first_callback = self.build.callbacks.first()
        first_callback.dispatch()
        self.assertTrue(requests_post.called)
        self.assertTrue(first_callback.is_sent)
        requests_post.assert_called_with(url1)

        last_callback = self.build.callbacks.last()
        last_callback.dispatch()
        self.assertTrue(requests_post.called)
        self.assertTrue(last_callback.is_sent)
        requests_post.assert_called_with(url2)

    @patch('requests.post')
    def test_build_callback_not_dispatched_more_than_once(self, requests_post):
        url = 'http://callback-target.com'

        callback = self.build.callbacks.create(url=url, event=self.event)
        callback.dispatch()

        self.assertTrue(requests_post.called)
        self.assertTrue(callback.is_sent)

        requests_post.reset_mock()
        callback.dispatch()
        self.assertFalse(requests_post.called)

    @patch('requests.post')
    def test_build_callback_gets_deleted_on_build_deletion(self, requests_post):
        url = 'http://callback-target.com'
        build = self.project.builds.create(version='to-be-deleted')

        callback = build.callbacks.create(url=url, event=self.event)
        build.delete()

        with self.assertRaises(Callback.DoesNotExist):
            callback.refresh_from_db()

    def test_malformed_callback(self):
        callback = Callback(object_reference=self.build, url='invalid-url')
        with self.assertRaises(ValidationError):
            callback.full_clean()

        callback = Callback(object_reference=self.build, event='weird-event')
        with self.assertRaises(ValidationError):
            callback.full_clean()

    def test_duplicated_callback(self):
        self.build.callbacks.create(url='http://callback.url')
        with self.assertRaises(IntegrityError):
            self.build.callbacks.create(url='http://callback.url')
