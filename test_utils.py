import decorator
import mwapi # type: ignore
import pytest # type: ignore
import requests
import requests_oauthlib # type: ignore
from typing import Callable, TypeVar


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


Ret = TypeVar('Ret')


@decorator.decorator
def internet_test(func: Callable[..., Ret], *args, **kwargs) -> Ret:
    """Decorator for a test that accesses the internet.

    If the test raises a ConnectionError, the test is marked as
    skipped instead of failed.
    """
    try:
        return func(*args, **kwargs)
    except mwapi.errors.ConnectionError:
        return pytest.skip('no internet connection') # does not actually return, but mypy wants a return statement
