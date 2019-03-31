import requests
import requests_oauthlib # type: ignore


class FakeSession:

    def __init__(self, get_response, post_response=None):
        self.get_response = get_response
        self.post_response = post_response
        self.host = None
        self.session = requests.Session()
        self.session.auth = requests_oauthlib.OAuth1(client_key='fake client key', client_secret='fake client secret',
                                                     resource_owner_key='fake resource owner key', resource_owner_secret='fake resource owner secret')

    def get(self, *args, **kwargs):
        return self.get_response

    def post(self, *args, **kwargs):
        if self.post_response:
            if isinstance(self.post_response, BaseException):
                raise self.post_response
            else:
                return self.post_response
        else:
            raise NotImplementedError
