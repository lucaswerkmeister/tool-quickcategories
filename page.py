from dataclasses import dataclass, KW_ONLY
from typing import Optional


@dataclass
class Page:
    """A specifier for a page on a wiki, optionally resolved."""

    title: str
    _: KW_ONLY
    resolve_redirects: Optional[bool]  # None means “batch predates this flag” and is to be interpreted as False in accordance with the original code’s behavior
    create_missing_page: Optional[bool]  # ditto (None also means False)
    resolution: Optional[dict] = None

    def cleanup(self) -> None:
        """Partially normalize the page, as a convenience for users.

        This should not be used as a replacement for full
        normalization via the MediaWiki API.
        """
        self.title = self.title.replace('_', ' ')

    def __str__(self) -> str:
        flags = [
            f'resolve_redirects={'yes' if self.resolve_redirects else 'no'}',
            f'create_missing_page={'yes' if self.create_missing_page else 'no'}',
        ]
        return self.title + (f'#{','.join(flags)}' if flags else '')
