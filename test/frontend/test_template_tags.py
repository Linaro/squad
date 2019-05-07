import urllib.parse
from jinja2 import Template


from django.test import TestCase


from squad.frontend.templatetags.squad import get_page_url


class FakeRequest():
    pass


class FakeGet():

    def __init__(self, params=None):
        self.params = params or {}

    def update(self, params):
        self.params.update(**params)

    def copy(self):
        return self

    def urlencode(self):
        return urllib.parse.urlencode(self.params)


class TemplateTagsTest(TestCase):

    def test_get_page_url(self):
        fake_request = FakeRequest()
        fake_request.GET = FakeGet({'page': 2, 'existing_arg': 'val'})
        context = {'request': fake_request, 'get_page_url': get_page_url}

        template_to_render = Template('{{get_page_url(42)}}')
        rendered_template = template_to_render.render(context)
        self.assertNotIn('page=2', rendered_template)
        self.assertIn('page=42', rendered_template)
        self.assertIn('existing_arg=val', rendered_template)
