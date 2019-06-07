import json
from django.test import Client


class JSONResponse(object):
    def __init__(self, response):
        self.http = response

        body = response.content or bytes('{}', 'utf-8')
        self.data = json.loads(body.decode('utf-8'))


class APIClient(Client):

    def __init__(self, token):
        self.token = token
        return super(APIClient, self).__init__(token)

    def post(self, *args, **kwargs):
        return self.__request__('post', *args, **kwargs)

    def get(self, *args, **kwargs):
        return self.__request__('get', *args, **kwargs)

    def get_json(self, *args, **kwargs):
        resp = self.get(*args, **kwargs)
        return JSONResponse(resp)

    def __request__(self, method, *args, **kwargs):
        if not kwargs.get('HTTP_AUTH_TOKEN'):
            kwargs = kwargs.copy()
            kwargs.update({'HTTP_AUTH_TOKEN': self.token})
        m = getattr(super(APIClient, self), method)
        return m(*args, **kwargs)


class RestAPIClient(APIClient):

    def __request__(self, method, *args, **kwargs):
        if not kwargs.get('HTTP_AUTHORIZATION'):
            kwargs = kwargs.copy()
            kwargs.update({'HTTP_AUTHORIZATION': "Token %s" % self.token})
        m = getattr(super(APIClient, self), method)
        return m(*args, **kwargs)
