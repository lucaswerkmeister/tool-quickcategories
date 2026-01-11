import pytest

from page import Page


def test_Page_cleanup() -> None:
    page = Page('Page_from_URL', resolve_redirects=True, create_missing_page=False)
    page.cleanup()
    assert page == Page('Page from URL', resolve_redirects=True, create_missing_page=False)

@pytest.mark.parametrize('page, expected', [
    # the expected strings always include the flags, even if they’re originally None,
    # so that exporting a batch to TPSV and then recreating it will always preserve the flags,
    # regardless of the default flags set when the batch is being recreated
    (Page('Page', resolve_redirects=None, create_missing_page=None), 'Page#resolve_redirects=no,create_missing_page=no'),
    (Page('Page', resolve_redirects=False, create_missing_page=True), 'Page#resolve_redirects=no,create_missing_page=yes'),
    (Page('Page', resolve_redirects=True, create_missing_page=False), 'Page#resolve_redirects=yes,create_missing_page=no'),
    (Page('Page', resolve_redirects=True, create_missing_page=True), 'Page#resolve_redirects=yes,create_missing_page=yes'),
])
def test_Page_str(page: Page, expected: str) -> None:
    assert str(page) == expected
