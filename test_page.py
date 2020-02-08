from action import AddCategoryAction
from page import Page


page1 = Page('Page 1')
page2 = Page('Page 2')


def test_Page_cleanup():
    page = Page('Page_from_URL')
    page.cleanup()
    assert page == Page('Page from URL')

def test_Page_eq_same():
    assert page1 == page1

def test_Page_eq_equal():
    assert page1 == Page(page1.title)

def test_Page_eq_different_type():
    assert page1 != AddCategoryAction('Page 1')

def test_Page_eq_different_title():
    assert page1 != Page('Page A')
    assert page1 != Page('Page_1')

def test_Page_str():
    assert str(page1) == 'Page 1'

def test_Page_repr():
    assert eval(repr(page1)) == page1
