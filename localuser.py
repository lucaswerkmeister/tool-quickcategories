from dataclasses import dataclass, field


@dataclass(frozen=True)
class LocalUser:
    """A user account local to one wiki."""

    user_name: str = field(compare=False)  # ignored in __eq__, to account for renamed users
    domain: str
    local_user_id: int
    global_user_id: int

    def __str__(self) -> str:
        return self.user_name + '@' + self.domain
