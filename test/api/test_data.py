from django.test import TestCase
import json
from unittest.mock import patch

from django.contrib.auth.models import User

from test.api import Client, APIClient
from squad.core.tasks import ReceiveTestRun
from squad.core import models


class ApiDataTest(TestCase):

    def setUp(self):
        self.group = models.Group.objects.create(slug='mygroup')
        self.project = self.group.projects.create(slug='myproject')
        self.project.tokens.create(key='thekey')
        self.client = APIClient('thekey')

    def receive(self, datestr, metrics):
        receive = ReceiveTestRun(self.project)
        receive(
            version=datestr,
            environment_slug="env1",
            metadata=json.dumps({"datetime": datestr + "T00:00:00+00:00"}),
            metrics_file=json.dumps(metrics),
        )

    def test_basics(self):
        self.receive("2016-09-01", {
            "foo": 1,
            "bar/baz": 2,
        })

        self.receive("2016-09-02", {
            "foo": 2,
            "bar/baz": 3,
        })

        resp = self.client.get_json('/api/data/mygroup/myproject?metric=foo&metric=bar/baz&environment=env1')
        json = resp.data
        self.assertEqual(dict, type(json['foo']))

        first = json['foo']['env1'][0]
        second = json['foo']['env1'][1]
        self.assertEqual([1472688000, 1.0], first[0:2])
        self.assertEqual([1472774400, 2.0], second[0:2])

        first = json['bar/baz']['env1'][0]
        second = json['bar/baz']['env1'][1]
        self.assertEqual([1472688000, 2.0], first[0:2])
        self.assertEqual([1472774400, 3.0], second[0:2])

        self.assertEqual('application/json; charset=utf-8', resp.http['Content-Type'])

    def test_no_auth(self):
        unauthenticated_client = Client()
        resp = unauthenticated_client.get('/api/data/mygroup/myproject?metric=foo&metric=bar/baz&environment=env1')
        self.assertEqual(401, resp.status_code)

    @patch("squad.api.data.PUBLIC_SITE", True)
    def test_no_auth_on_public_site(self):
        unauthenticated_client = Client()
        resp = unauthenticated_client.get('/api/data/mygroup/myproject?metric=foo&metric=bar/baz&environment=env1')
        self.assertEqual(200, resp.status_code)

    def test_invalid_auth(self):
        wrong_client = APIClient('invalidkey')
        resp = wrong_client.get('/api/data/mygroup/myproject?metric=foo&metric=bar/baz&environment=env1')
        self.assertEqual(401, resp.status_code)

    def test_auth_from_web_ui(self):
        web_client = Client()
        user = User.objects.create(username='theuser')
        web_client.force_login(user)

        resp = web_client.get('/api/data/mygroup/myproject?metric=foo&metric=bar/baz&environment=env1')
        self.assertEqual(200, resp.status_code)
