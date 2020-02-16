from action import AddCategoryAction
from page import Page


page1 = Page('Page 1', True)
page2 = Page('Page 2', False)


def test_Page_cleanup():
    page = Page('Page_from_URL', True)
    page.cleanup()
    assert page == Page('Page from URL', True)

def test_Page_eq_same():
    assert page1 == page1

def test_Page_eq_equal():
    assert page1 == Page(page1.title, page1.resolve_redirects)

def test_Page_eq_different_type():
    assert page1 != AddCategoryAction('Page 1')

def test_Page_eq_different_title():
    assert page1 != Page('Page A', page1.resolve_redirects)
    assert page1 != Page('Page_1', page1.resolve_redirects)

def test_Page_eq_different_resolve_redirects():
    assert page1 != Page(page1.title, False)
    assert page1 != Page(page1.title, None)
    assert page1 != Page(page1.title, 1)

def test_Page_str():
    assert str(page1) == 'Page 1'
    assert str(page2) == '!Page 2'

def test_Page_repr():
    assert eval(repr(page1)) == page1
    assert eval(repr(page2)) == page2
