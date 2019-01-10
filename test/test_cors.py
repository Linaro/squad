from django.test import Client, TestCase


class CrossOriginResourceSharingTest(TestCase):

    def setUp(self):
        client = Client()
        self.response = client.options('/', {}, **{'HTTP_ORIGIN': 'https://www.example.com/'})

    def test_allow_origin(self):
        self.assertEqual('*', self.response['Access-Control-Allow-Origin'])

    def test_allow_methods(self):
        self.assertEqual('GET, HEAD', self.response['Access-Control-Allow-Methods'])
