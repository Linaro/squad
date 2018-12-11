from django.test import TestCase
import json
from unittest.mock import patch

from django.contrib.auth.models import User, Group

from test.api import Client, APIClient
from squad.core.tasks import ReceiveTestRun
from squad.core import models


class ApiDataTest(TestCase):

    def setUp(self):
        self.user_group = Group.objects.create(name='foo')
        self.group = models.Group.objects.create(slug='mygroup')
        self.group.user_groups.add(self.user_group)
        self.project = self.group.projects.create(slug='myproject')
        self.project.tokens.create(key='thekey')
        self.client = APIClient('thekey')

    def receive(self, datestr, metrics={}, tests={}):
        receive = ReceiveTestRun(self.project)
        receive(
            version=datestr,
            environment_slug="env1",
            metadata_file=json.dumps({"datetime": datestr + "T00:00:00+00:00", "job_id": '1'}),
            metrics_file=json.dumps(metrics),
            tests_file=json.dumps(tests),
        )

    def test_basics(self):
        self.receive("2016-09-01", metrics={
            "foo": 1,
            "bar/baz": 2,
        })

        self.receive("2016-09-02", metrics={
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

    def test_metrics_csv(self):
        self.receive("2018-09-17", metrics={
            "foo": 1,
            "bar/baz": 2,
        })

        self.receive("2018-09-18", metrics={
            "foo": 2,
            "bar/baz": 3,
        })

        resp = self.client.get('/api/data/mygroup/myproject?metric=foo&environment=env1&format=csv')
        data = resp.content.decode('utf-8').split("\n")
        self.assertIn('"foo","env1","1537142400","1.0","2018-09-17",""', data[0])
        self.assertIn('"foo","env1","1537228800","2.0","2018-09-18",""', data[1])

    def test_tests(self):
        self.receive("2017-01-01", tests={
            "foo": "pass",
            "bar": "fail",
        })
        self.receive("2017-01-02", tests={
            "foo": "pass",
            "bar": "pass",
        })

        response = self.client.get_json('/api/data/mygroup/myproject?metric=:tests:&environment=env1')
        json = response.data

        first = json[':tests:']['env1'][0]
        second = json[':tests:']['env1'][1]

        self.assertEqual([1483228800, 50, '2017-01-01', ''], first)
        self.assertEqual([1483315200, 100, '2017-01-02', ''], second)

    def test_no_auth_on_non_public_project(self):
        self.project.is_public = False
        self.project.save()

        unauthenticated_client = Client()
        resp = unauthenticated_client.get('/api/data/mygroup/myproject?metric=foo&metric=bar/baz&environment=env1')
        self.assertEqual(401, resp.status_code)

    def test_no_auth_on_public_project(self):
        unauthenticated_client = Client()
        resp = unauthenticated_client.get('/api/data/mygroup/myproject?metric=foo&metric=bar/baz&environment=env1')
        self.assertEqual(200, resp.status_code)

    def test_invalid_auth(self):
        self.project.is_public = False
        self.project.save()

        wrong_client = APIClient('invalidkey')
        resp = wrong_client.get('/api/data/mygroup/myproject?metric=foo&metric=bar/baz&environment=env1')
        self.assertEqual(401, resp.status_code)

    def test_auth_from_web_ui(self):
        self.project.is_public = False
        self.project.save()

        web_client = Client()
        user = User.objects.create(username='theuser')
        user.groups.add(self.user_group)
        web_client.force_login(user)

        resp = web_client.get('/api/data/mygroup/myproject?metric=foo&metric=bar/baz&environment=env1')
        self.assertEqual(200, resp.status_code)

    def test_all_metrics(self):
        self.receive("2018-09-01", metrics={
            "foo": 1,
            "bar/baz": 2,
        })

        self.receive("2018-09-02", metrics={
            "foo": 2,
            "bar/baz": 3,
        })

        resp = self.client.get_json(
            '/api/data/mygroup/myproject?environment=env1')
        json = resp.data
        self.assertEqual(dict, type(json['foo']))
        self.assertEqual(dict, type(json['bar/baz']))

        first = json['foo']['env1'][0]
        second = json['foo']['env1'][1]
        self.assertEqual([1535760000, 1.0], first[0:2])
        self.assertEqual([1535846400, 2.0], second[0:2])

        first = json['bar/baz']['env1'][0]
        second = json['bar/baz']['env1'][1]
        self.assertEqual([1535760000, 2.0], first[0:2])
        self.assertEqual([1535846400, 3.0], second[0:2])

        self.assertEqual('application/json; charset=utf-8', resp.http['Content-Type'])
