import urllib.parse
from jinja2 import Template


from django.test import TestCase
from django.test.client import RequestFactory
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.providers.google.provider import GoogleProvider
from allauth.socialaccount.providers.github.provider import GitHubProvider
from allauth.socialaccount.providers.gitlab.provider import GitLabProvider

from squad.core import models
from squad.frontend.templatetags.squad import get_page_url, project_status, strip_get_parameters, update_get_parameters, to_json, socialaccount_providers


class FakeRequest():
    pass


class FakeGet():

    def __init__(self, params=None):
        self.params = params or {}

    def __setitem__(self, key, value):
        self.params[key] = value

    def __getitem__(self, key):
        return self.params.get(key)

    def __delitem__(self, key):
        del self.params[key]

    def get(self, key):
        return self.__getitem__(key)

    def keys(self):
        return self.params.keys()

    def copy(self):
        return self

    def urlencode(self):
        return urllib.parse.urlencode(self.params)


class TemplateTagsTest(TestCase):

    def test_strip_get_parameters(self):
        fake_request = FakeRequest()
        fake_request.GET = FakeGet({'page': 2, 'existing_arg': 'val'})
        context = {'request': fake_request}
        result = strip_get_parameters(context, ['page'])
        self.assertIn('existing_arg', result)
        self.assertNotIn('page', result)

    def test_update_get_parameters(self):
        fake_request = FakeRequest()
        fake_request.GET = FakeGet({'page': 2, 'existing_arg': 'val'})
        context = {'request': fake_request}
        result = update_get_parameters(context, {'page': 42})
        self.assertIn('existing_arg', result)
        self.assertIn('page=42', result)

    def test_get_page_url(self):
        fake_request = FakeRequest()
        fake_request.GET = FakeGet({'page': 2, 'existing_arg': 'val'})
        context = {'request': fake_request, 'get_page_url': get_page_url}

        template_to_render = Template('{{get_page_url(42)}}')
        rendered_template = template_to_render.render(context)
        self.assertNotIn('page=2', rendered_template)
        self.assertIn('page=42', rendered_template)
        self.assertIn('existing_arg=val', rendered_template)

    def test_to_json(self):
        self.assertEqual('1', to_json(1))
        self.assertEqual('"a string"', to_json('a string'))
        self.assertEqual('[1, 2, 3]', to_json([1, 2, 3]))
        self.assertEqual('{"key": 42}', to_json({'key': 42}))
        self.assertEqual('', to_json(FakeGet()))  # non-parsable types return empty string

    def test_socialaccount_providers_google(self):
        s = SocialApp.objects.create(
            name="foo",
            client_id="ID_123456789",
            secret="secret_987654321",
            provider=GoogleProvider.id
        )
        s.save()
        site = Site.objects.first()
        s.sites.add(site)
        s.save()

        factory = RequestFactory()
        context = {"request": factory.get("/login")}
        social_providers = socialaccount_providers(context)
        self.assertEqual(1, len(social_providers.keys()))
        self.assertEqual(GoogleProvider, list(social_providers)[0].__class__)

    def test_socialaccount_providers_github(self):
        s = SocialApp.objects.create(
            name="foo",
            client_id="ID_123456789",
            secret="secret_987654321",
            provider=GitHubProvider.id
        )
        s.save()
        site = Site.objects.first()
        s.sites.add(site)
        s.save()

        factory = RequestFactory()
        context = {"request": factory.get("/login")}
        social_providers = socialaccount_providers(context)
        self.assertEqual(1, len(social_providers.keys()))
        self.assertEqual(GitHubProvider, list(social_providers)[0].__class__)

    def test_socialaccount_providers_gitlab(self):
        s = SocialApp.objects.create(
            name="foo",
            client_id="ID_123456789",
            secret="secret_987654321",
            provider=GitLabProvider.id
        )
        s.save()
        site = Site.objects.first()
        s.sites.add(site)
        s.save()

        factory = RequestFactory()
        context = {"request": factory.get("/login")}
        social_providers = socialaccount_providers(context)
        self.assertEqual(1, len(social_providers.keys()))
        self.assertEqual(GitLabProvider, list(social_providers)[0].__class__)

    def test_catch_error_when_status_missing(self):
        # Test that if the status for a build gets deleted, that this is
        # handled appropriately, rather than causing a crash.

        # create the group, project and build
        self.group = models.Group.objects.create(slug="mygroup")
        self.project = self.group.projects.create(slug="myproject")
        self.build = self.project.builds.create(version="mybuild")
        self.project.latest_build = self.build

        # Set build status to None
        self.build.status = None

        # Try to call project_status when status is None
        missing_project_status_error = False
        try:
            status = project_status(self.project)
        except models.Build.status.RelatedObjectDoesNotExist:
            missing_project_status_error = True

        # Check call to project_status doesn't crash
        self.assertFalse(missing_project_status_error)
        # Check status returns None as expected
        self.assertEqual(status, None)
