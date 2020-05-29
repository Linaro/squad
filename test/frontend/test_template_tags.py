import urllib.parse
from jinja2 import Template


from django.test import TestCase


from squad.frontend.templatetags.squad import get_page_url, strip_get_parameters, update_get_parameters, to_json


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
