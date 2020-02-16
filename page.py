from typing import Any, Optional


class Page:
    """A specifier for a page on a wiki, optionally resolved."""

    title: str
    resolve_redirects: Optional[bool]
    resolution: Optional[dict] = None

    def __init__(self, title: str, resolve_redirects: Optional[bool]):
        if title.startswith('!'):
            raise ValueError("page title '%s' cannot start with ! (ambiguous str)" % title)
        self.title = title
        self.resolve_redirects = resolve_redirects

    def cleanup(self) -> None:
        """Partially normalize the page, as a convenience for users.

        This should not be used as a replacement for full
        normalization via the MediaWiki API.
        """
        self.title = self.title.replace('_', ' ')

    def __eq__(self, value: Any) -> bool:
        return type(value) is Page and \
            self.title == value.title and \
            self.resolve_redirects is value.resolve_redirects

    def __str__(self) -> str:
        if self.resolve_redirects is False:
            return '!' + self.title
        else:
            return self.title

    def __repr__(self) -> str:
        return 'Page(' + repr(self.title) + ', ' + repr(self.resolve_redirects) + ')'
