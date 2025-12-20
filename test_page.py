from page import Page


page1 = Page('Page 1', resolve_redirects=True)
page2 = Page('Page 2', resolve_redirects=False)


def test_Page_cleanup() -> None:
    page = Page('Page_from_URL', resolve_redirects=True)
    page.cleanup()
    assert page == Page('Page from URL', resolve_redirects=True)

def test_Page_str() -> None:
    assert str(page1) == 'Page 1'
    assert str(page2) == '!Page 2'
