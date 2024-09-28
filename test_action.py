import pytest
from typing import Type

from action import AddCategoryAction, AddCategoryAndSortKeyAction, AddCategoryWithSortKeyAction, AddCategoryProvideSortKeyAction, AddCategoryReplaceSortKeyAction, CategoryAction, RemoveCategoryAction, RemoveCategoryWithSortKeyAction


addCategory1 = AddCategoryAction('Cat 1')
addCategory2 = AddCategoryAction('Cat 2')
addCategoryWithSortKey1 = AddCategoryWithSortKeyAction('Cat 1', 'sort key')
addCategoryProvideSortKey1 = AddCategoryProvideSortKeyAction('Cat 1', 'sort key')
addCategoryReplaceSortKey1 = AddCategoryReplaceSortKeyAction('Cat 1', 'sort key')
removeCategory1 = RemoveCategoryAction('Cat 1')
removeCategoryWithSortKey1 = RemoveCategoryWithSortKeyAction('Cat 1', 'sort key')


@pytest.mark.parametrize('class_', [AddCategoryAction, RemoveCategoryAction])
def test_CategoryAction_init_empty(class_: Type[CategoryAction]) -> None:
    with pytest.raises(AssertionError):
        class_('')

@pytest.mark.parametrize('class_', [AddCategoryAction, RemoveCategoryAction])
def test_CategoryAction_init_wikilink(class_: Type[CategoryAction]) -> None:
    with pytest.raises(AssertionError):
        class_('[[Category:Cat 1]]')
    with pytest.raises(AssertionError):
        class_('[[other link]]')

@pytest.mark.parametrize('class_', [AddCategoryAction, RemoveCategoryAction])
def test_CategoryAction_init_category_namespace(class_: Type[CategoryAction]) -> None:
    with pytest.raises(AssertionError):
        class_('Category:Cat 1')


@pytest.mark.parametrize('wikitext, expected', [
    ('', '[[Category:Test]]'),
    ('end of article', 'end of article\n[[Category:Test]]'),
    ('end of article\n[[Category:A]]\n[[Category:B]]', 'end of article\n[[Category:A]]\n[[Category:B]]\n[[Category:Test]]'),
    ('some wikitext\n[[Category:Here]]\nmore wikitext', 'some wikitext\n[[Category:Here]]\n[[Category:Test]]\nmore wikitext'),
    ('it is [[Category:Test]] already present', 'it is [[Category:Test]] already present'),
    ('it is [[Category:test]] already present in lowercase', 'it is [[Category:test]] already present in lowercase'),
    ('it is [[Category:TEST]] present in different capitalization', 'it is [[Category:TEST]]\n[[Category:Test]] present in different capitalization'),
    ('[[Kategorie:Test]]', '[[Kategorie:Test]]'),
    ('[[K:Test]]', '[[K:Test]]'),
    ('[[Category:Test|sort key]]', '[[Category:Test|sort key]]'),
    ('[[:Category:Test]]', '[[:Category:Test]]\n[[Category:Test]]'),
    ('[[:Category:Test|link text]]', '[[:Category:Test|link text]]\n[[Category:Test]]'),
    ('<nowiki>[[Category:Test]]</nowiki>', '<nowiki>[[Category:Test]]</nowiki>\n[[Category:Test]]'),
    ('[[Test]]', '[[Test]]\n[[Category:Test]]'),
    ('[[Special:Test]]', '[[Special:Test]]\n[[Category:Test]]'),
])
def test_AddCategoryAction_apply(wikitext: str, expected: str) -> None:
    action = AddCategoryAction('Test')
    actual = action.apply(wikitext, ('Category', ['Category', 'Kategorie', 'K'], 'first-letter'))
    assert expected == actual

@pytest.mark.parametrize('wikitext, category', [
    # note: test_RemoveCategoryAction_apply_whitespace has a copy of these test cases
    ('[[Category:A]]', ' A '),
    ('[[Category: A ]]', 'A'),
    ('[[Category:My_Test_Category]]', 'My Test Category'),
    ('[[Category:My Test Category]]', 'My_Test_Category'),
    ('[[Category:A B]]', 'A\u00a0B'),
    ('[[Category:A\u00a0B]]', 'A B'),
])
def test_AddCategoryAction_apply_whitespace(wikitext: str, category: str) -> None:
    action = AddCategoryAction(category)
    assert wikitext == action.apply(wikitext, ('Category', ['Category'], 'first-letter'))

# note: the following test is no longer as relevant since we clean up all new batches to never contain underscores
def test_AddCategoryAction_apply_preserves_underscores() -> None:
    action1 = AddCategoryAction('Test Category 1')
    action2 = AddCategoryAction('Test_Category_2')
    action3 = AddCategoryAction('Test_Category 3')
    expected = '[[Category:Test Category 1]]\n[[Category:Test_Category_2]]\n[[Category:Test_Category 3]]'
    actual = ''
    for action in [action1, action2, action3]:
        actual = action.apply(actual, ('Category', ['Category'], 'first-letter'))
    assert expected == actual

def test_AddCategoryAction_apply_case_sensitive() -> None:
    action = AddCategoryAction('Test')
    wikitext = '[[Category:test]]'
    expected = '[[Category:test]]\n[[Category:Test]]'
    assert expected == action.apply(wikitext, ('Category', ['Category'], 'case-sensitive'))

def test_AddCategoryAction_summary() -> None:
    assert AddCategoryAction('Test').summary(('Kategorie', ['Kategorie', 'Category'], 'first-letter')) == '+[[Kategorie:Test]]'

def test_AddCategoryAction_is_minor() -> None:
    assert AddCategoryAction('Test').is_minor()

def test_AddCategoryAction_cleanup() -> None:
    action = AddCategoryAction('User_input_from_URL')
    action.cleanup()
    assert action == AddCategoryAction('User input from URL')

def test_AddCategoryAction_str() -> None:
    assert str(addCategory1) == '+Category:Cat 1'


@pytest.mark.parametrize('class_', [AddCategoryWithSortKeyAction, AddCategoryProvideSortKeyAction, AddCategoryReplaceSortKeyAction])
def test_AddCategoryAndSortKeyAction_init_empty_sort_key(class_: Type[AddCategoryAndSortKeyAction]) -> None:
    with pytest.raises(AssertionError):
        class_('Category', '')

@pytest.mark.parametrize('class_', [AddCategoryWithSortKeyAction, AddCategoryProvideSortKeyAction, AddCategoryReplaceSortKeyAction])
def test_AddCategoryAndSortKeyAction_summary(class_: Type[AddCategoryAndSortKeyAction]) -> None:
    assert class_('Test', 'Sortierschlüssel').summary(('Kategorie', ['Kategorie', 'Category'], 'first-letter')) == '+[[Kategorie:Test|Kategorie:Test|Sortierschlüssel]]'


@pytest.mark.parametrize('wikitext, expected', [
    ('', '[[Category:Test|sort key]]'),
    ('[[Category:Test]]', '[[Category:Test]]'),
    ('[[Category:Test|other sort key]]', '[[Category:Test|other sort key]]'),
])
def test_AddCategoryWithSortKeyAction_apply(wikitext: str, expected: str) -> None:
    action = AddCategoryWithSortKeyAction('Test', 'sort key')
    actual = action.apply(wikitext, ('Category', ['Category', 'Kategorie', 'K'], 'first-letter'))
    assert expected == actual

def test_AddCategoryWithSortKeyAction_str() -> None:
    assert str(addCategoryWithSortKey1) == '+Category:Cat 1#sort key'


@pytest.mark.parametrize('wikitext, expected', [
    ('', '[[Category:Test|sort key]]'),
    ('[[Category:Test]]', '[[Category:Test|sort key]]'),
    ('[[Category:Test|other sort key]]', '[[Category:Test|other sort key]]'),
])
def test_AddCategoryProvideSortKeyAction_apply(wikitext: str, expected: str) -> None:
    action = AddCategoryProvideSortKeyAction('Test', 'sort key')
    actual = action.apply(wikitext, ('Category', ['Category', 'Kategorie', 'K'], 'first-letter'))
    assert expected == actual

def test_AddCategoryProvideSortKeyAction_str() -> None:
    assert str(addCategoryProvideSortKey1) == '+Category:Cat 1##sort key'


@pytest.mark.parametrize('wikitext, expected', [
    ('', '[[Category:Test|sort key]]'),
    ('[[Category:Test]]', '[[Category:Test|sort key]]'),
    ('[[Category:Test|other sort key]]', '[[Category:Test|sort key]]'),
])
def test_AddCategoryReplaceSortKeyAction_apply(wikitext: str, expected: str) -> None:
    action = AddCategoryReplaceSortKeyAction('Test', 'sort key')
    actual = action.apply(wikitext, ('Category', ['Category', 'Kategorie', 'K'], 'first-letter'))
    assert expected == actual

def test_AddCategoryReplaceSortKeyAction_apply_remove_sort_key() -> None:
    action = AddCategoryReplaceSortKeyAction('Test', None)
    wikitext = '[[Category:Test|sort key]]'
    expected = '[[Category:Test]]'
    actual = action.apply(wikitext, ('Category', ['Category', 'Kategorie', 'K'], 'first-letter'))
    assert expected == actual

def test_AddCategoryReplaceSortKeyAction_str() -> None:
    assert str(addCategoryReplaceSortKey1) == '+Category:Cat 1###sort key'


@pytest.mark.parametrize('wikitext, expected', [
    ('', ''),
    ('[[Category:Test]]', ''),
    ('end of article\n[[Category:Test]]', 'end of article'),
    ('[[Category:Test]]\nbeginning of article', 'beginning of article'),
    ('[[Category:Start]][[Category:Test]][[Category:End]]', '[[Category:Start]][[Category:End]]'),
    ('[[Category:Start]]\n[[Category:Test]]\n[[Category:End]]', '[[Category:Start]]\n[[Category:End]]'),
    ('[[Category:test]]', ''),
    ('[[Kategorie:Test]]', ''),
    ('[[K:Test]]', ''),
    ('[[Category:Test|sort key]]', ''),
    ('[[:Category:Test]]', '[[:Category:Test]]'),
    ('[[:Category:Test|link text]]', '[[:Category:Test|link text]]'),
    ('<nowiki>[[Category:Test]]</nowiki>', '<nowiki>[[Category:Test]]</nowiki>'),
    ('[[Test]]', '[[Test]]'),
    ('[[Special:Test]]', '[[Special:Test]]'),
])
def test_RemoveCategoryAction_apply(wikitext: str, expected: str) -> None:
    action = RemoveCategoryAction('Test')
    actual = action.apply(wikitext, ('Category', ['Category', 'Kategorie', 'K'], 'first-letter'))
    assert expected == actual

@pytest.mark.parametrize('wikitext, category', [
    # note: test_AddCategoryAction_apply_whitespace has a copy of these test cases
    ('[[Category:A]]', ' A '),
    ('[[Category: A ]]', 'A'),
    ('[[Category:My_Test_Category]]', 'My Test Category'),
    ('[[Category:My Test Category]]', 'My_Test_Category'),
    ('[[Category:A B]]', 'A\u00a0B'),
    ('[[Category:A\u00a0B]]', 'A B'),
])
def test_RemoveCategoryAction_apply_whitespace(wikitext: str, category: str) -> None:
    action = RemoveCategoryAction(category)
    actual = action.apply(wikitext, ('Category', ['Category'], 'first-letter'))
    assert '' == actual

def test_RemoveCategoryAction_apply_case_sensitive() -> None:
    action = RemoveCategoryAction('Test')
    wikitext = '[[category:test]]'
    assert wikitext == action.apply(wikitext, ('Category', ['Category'], 'case-sensitive'))

def test_RemoveCategoryAction_summary() -> None:
    assert RemoveCategoryAction('Test').summary(('Kategorie', ['Kategorie', 'Category'], 'first-letter')) == '-[[Kategorie:Test]]'

def test_RemoveCategoryAction_is_minor() -> None:
    assert not RemoveCategoryAction('Test').is_minor()

def test_RemoveCategoryAction_cleanup() -> None:
    action = RemoveCategoryAction('User_input_from_URL')
    action.cleanup()
    assert action == RemoveCategoryAction('User input from URL')

def test_RemoveCategoryAction_str() -> None:
    assert str(removeCategory1) == '-Category:Cat 1'


def test_RemoveCategoryWithSortKeyAction_init_empty_sort_key() -> None:
    with pytest.raises(AssertionError):
        RemoveCategoryWithSortKeyAction('Category', '')

def test_RemoveCategoryWithSortKeyAction_summary() -> None:
    assert RemoveCategoryWithSortKeyAction('Test', 'Sortierschlüssel').summary(('Kategorie', ['Kategorie', 'Category'], 'first-letter')) == '-[[Kategorie:Test|Kategorie:Test|Sortierschlüssel]]'

@pytest.mark.parametrize('wikitext, expected', [
    ('', ''),
    ('[[Category:Test]]', '[[Category:Test]]'),
    ('[[Category:Test|sort key]]', ''),
])
def test_RemoveCategoryWithSortKeyAction_apply(wikitext: str, expected: str) -> None:
    action = RemoveCategoryWithSortKeyAction('Test', 'sort key')
    actual = action.apply(wikitext, ('Category', ['Category', 'Kategorie', 'K'], 'first-letter'))
    assert expected == actual

def test_RemoveCategoryWithSortKeyAction_str() -> None:
    assert str(removeCategoryWithSortKey1) == '-Category:Cat 1#sort key'
