from dataclasses import dataclass
from typing import Optional


@dataclass
class Page:
    """A specifier for a page on a wiki, optionally resolved."""

    title: str
    resolve_redirects: Optional[bool]
    resolution: Optional[dict] = None

    def __post_init__(self) -> None:
        if self.title.startswith('!'):
            raise ValueError("page title '%s' cannot start with ! (ambiguous str)" % self.title)

    def cleanup(self) -> None:
        """Partially normalize the page, as a convenience for users.

        This should not be used as a replacement for full
        normalization via the MediaWiki API.
        """
        self.title = self.title.replace('_', ' ')

    def __str__(self) -> str:
        if self.resolve_redirects is False:
            return '!' + self.title
        else:
            return self.title
