import pytest

from action import AddCategoryAction, RemoveCategoryAction


addCategory1 = AddCategoryAction('Cat 1')
removeCategory2 = RemoveCategoryAction('Cat 2')
addCategory3 = AddCategoryAction('Cat 3')


@pytest.mark.parametrize('clazz', [AddCategoryAction, RemoveCategoryAction])
def test_CategoryAction_init_empty(clazz):
    with pytest.raises(AssertionError):
        clazz('')

@pytest.mark.parametrize('clazz', [AddCategoryAction, RemoveCategoryAction])
def test_CategoryAction_init_wikilink(clazz):
    with pytest.raises(AssertionError):
        clazz('[[Category:Cat 1]]')
    with pytest.raises(AssertionError):
        clazz('[[other link]]')

@pytest.mark.parametrize('clazz', [AddCategoryAction, RemoveCategoryAction])
def test_CategoryAction_init_category_namespace(clazz):
    with pytest.raises(AssertionError):
        clazz('Category:Cat 1')


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
def test_AddCategoryAction_apply(wikitext, expected):
    action = AddCategoryAction('Test')
    actual = action.apply(wikitext, ('Category', ['Category', 'Kategorie', 'K'], 'first-letter'))
    assert expected == actual

def test_AddCategoryAction_apply_detects_underscores():
    action = AddCategoryAction('My Test Category')
    wikitext = '[[Category:My_Test_Category]]'
    assert wikitext == action.apply(wikitext, ('Category', ['Category'], 'first-letter'))

# note: the following test is no longer as relevant since we clean up all new batches to never contain underscores
def test_AddCategoryAction_apply_preserves_underscores():
    action1 = AddCategoryAction('Test Category 1')
    action2 = AddCategoryAction('Test_Category_2')
    action3 = AddCategoryAction('Test_Category 3')
    expected = '[[Category:Test Category 1]]\n[[Category:Test_Category_2]]\n[[Category:Test_Category 3]]'
    actual = ''
    for action in [action1, action2, action3]:
        actual = action.apply(actual, ('Category', ['Category'], 'first-letter'))
    assert expected == actual

def test_AddCategoryAction_apply_case_sensitive():
    action = AddCategoryAction('Test')
    wikitext = '[[Category:test]]'
    expected = '[[Category:test]]\n[[Category:Test]]'
    assert expected == action.apply(wikitext, ('Category', ['Category'], 'case-sensitive'))

def test_AddCategoryAction_summary():
    assert AddCategoryAction('Test').summary(('Kategorie', ['Kategorie', 'Category'])) == '+[[Kategorie:Test]]'

def test_AddCategoryAction_cleanup():
    action = AddCategoryAction('User_input_from_URL')
    action.cleanup()
    assert action == AddCategoryAction('User input from URL')

def test_AddCategoryAction_eq_same():
    assert addCategory1 == addCategory1

def test_AddCategoryAction_eq_equal():
    assert addCategory1 == AddCategoryAction(addCategory1.category)

def test_AddCategoryAction_eq_different_type():
    assert addCategory1 != RemoveCategoryAction(addCategory1.category)
    assert addCategory1 is not None

def test_AddCategoryAction_eq_different_category():
    assert addCategory1 != addCategory3

def test_AddCategoryAction_eq_different_category_normalization():
    assert AddCategoryAction('Foo Bar') != AddCategoryAction('Foo_Bar')

def test_AddCategoryAction_str():
    assert str(addCategory1) == '+Category:Cat 1'

def test_AddCategoryAction_repr():
    assert eval(repr(addCategory1)) == addCategory1


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
def test_RemoveCategoryAction_apply(wikitext, expected):
    action = RemoveCategoryAction('Test')
    actual = action.apply(wikitext, ('Category', ['Category', 'Kategorie', 'K'], 'first-letter'))
    assert expected == actual

def test_RemoveCategoryAction_apply_case_sensitive():
    action = RemoveCategoryAction('Test')
    wikitext = '[[category:test]]'
    assert wikitext == action.apply(wikitext, ('Category', ['Category'], 'case-sensitive'))

def test_RemoveCategoryAction_summary():
    assert RemoveCategoryAction('Test').summary(('Kategorie', ['Kategorie', 'Category'])) == '-[[Kategorie:Test]]'

def test_RemoveCategoryAction_cleanup():
    action = RemoveCategoryAction('User_input_from_URL')
    action.cleanup()
    assert action == RemoveCategoryAction('User input from URL')

def test_RemoveCategoryAction_eq_same():
    assert removeCategory2 == removeCategory2

def test_RemoveCategoryAction_eq_equal():
    assert removeCategory2 == RemoveCategoryAction(removeCategory2.category)

def test_RemoveCategoryAction_eq_different_type():
    assert removeCategory2 != AddCategoryAction(removeCategory2.category)
    assert removeCategory2 is not None

def test_RemoveCategoryAction_eq_different_category():
    assert removeCategory2 != RemoveCategoryAction('Cat 4')

def test_RemoveCategoryAction_eq_different_category_normalization():
    assert RemoveCategoryAction('Foo Bar') != RemoveCategoryAction('Foo_Bar')

def test_RemoveCategoryAction_str():
    assert str(removeCategory2) == '-Category:Cat 2'

def test_RemoveCategoryAction_repr():
    assert eval(repr(removeCategory2)) == removeCategory2
