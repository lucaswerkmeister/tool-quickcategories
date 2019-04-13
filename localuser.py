from typing import Any


class LocalUser:
    """A user account local to one wiki."""

    def __init__(self, user_name: str, domain: str, local_user_id: int, global_user_id: int):
        self.user_name = user_name
        self.domain = domain
        self.local_user_id = local_user_id
        self.global_user_id = global_user_id

    def __eq__(self, value: Any) -> bool:
        # note: does not compare the user name, to account for renamed users
        return type(value) is LocalUser and \
            self.domain == value.domain and \
            self.local_user_id == value.local_user_id and \
            self.global_user_id == value.global_user_id

    def __str__(self) -> str:
        return self.user_name + '@' + self.domain

    def __repr__(self) -> str:
        return 'LocalUser(' + \
            repr(self.user_name) + ', ' + \
            repr(self.domain) + ', ' + \
            repr(self.local_user_id) + ', ' + \
            repr(self.global_user_id) + ')'
