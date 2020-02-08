from typing import Any, Optional


class Page:
    """A specifier for a page on a wiki, optionally resolved."""

    title: str
    resolution: Optional[dict] = None

    def __init__(self, title: str):
        self.title = title

    def cleanup(self) -> None:
        """Partially normalize the page, as a convenience for users.

        This should not be used as a replacement for full
        normalization via the MediaWiki API.
        """
        self.title = self.title.replace('_', ' ')

    def __eq__(self, value: Any) -> bool:
        return type(value) is Page and \
            self.title == value.title

    def __str__(self) -> str:
        return self.title

    def __repr__(self) -> str:
        return 'Page(' + repr(self.title) + ')'
