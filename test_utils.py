import requests
import requests_oauthlib  # type: ignore
from typing import Any, Callable, Optional


class FakeSession:

    host: Optional[str]

    def __init__(self, get_response: dict | BaseException | Callable, post_response: Optional[dict | BaseException | Callable] = None) -> None:
        self.get_response = get_response
        self.post_response = post_response
        self.host = None
        self.session = requests.Session()
        self.session.auth = requests_oauthlib.OAuth1(client_key='fake client key', client_secret='fake client secret',
                                                     resource_owner_key='fake resource owner key', resource_owner_secret='fake resource owner secret')

    def get(self, *args: Any, **kwargs: Any) -> dict:
        if callable(self.get_response):
            return self.get_response(*args, **kwargs)
        elif isinstance(self.get_response, BaseException):
            raise self.get_response
        else:
            return self.get_response

    def post(self, *args: Any, **kwargs: Any) -> dict:
        if self.post_response:
            if callable(self.post_response):
                return self.post_response(*args, **kwargs)
            elif isinstance(self.post_response, BaseException):
                raise self.post_response
            else:
                return self.post_response
        else:
            raise NotImplementedError
