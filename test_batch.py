import mwapi
import os
import pytest

from batch import Batch, Command, AddCategoryAction, RemoveCategoryAction


addCategory1 = AddCategoryAction('Cat 1')
removeCategory2 = RemoveCategoryAction('Cat 2')
addCategory3 = AddCategoryAction('Cat 3')
command1 = Command('Page 1', [addCategory1, removeCategory2])
command2 = Command('Page 2', [addCategory3])
batch1 = Batch({'foo': 'bar'}, [command1, command2])


def test_Batch_eq_same():
    assert batch1 == batch1

def test_Batch_eq_equal():
    assert batch1 == Batch(batch1.authentication, batch1.commands)

def test_Batch_eq_different_type():
    assert batch1 != command1
    assert batch1 != None

def test_Batch_eq_different_authentication():
    assert batch1 != Batch({'foo': 'baz'}, batch1.commands)

def test_Batch_eq_different_commands():
    assert batch1 != Batch(batch1.authentication, [command1])

def test_Batch_str():
    assert str(batch1) == '''
Page 1|+Category:Cat 1|-Category:Cat 2
Page 2|+Category:Cat 3
'''.strip()

def test_Batch_repr():
    assert eval(repr(batch1)) == batch1


def test_Command_apply():
    wikitext = 'Test page for the QuickCategories tool.\n[[Category:Already present cat]]\n[[Category:Removed cat]]\nBottom text'
    command = Command('Page title', [AddCategoryAction('Added cat'),
                                     AddCategoryAction('Already present cat'),
                                     RemoveCategoryAction('Removed cat'),
                                     RemoveCategoryAction('Not present cat')])
    new_wikitext, actions = command.apply(wikitext, ('Category', ['Category']))
    assert new_wikitext == 'Test page for the QuickCategories tool.\n[[Category:Already present cat]]\n[[Category:Added cat]]\nBottom text'
    assert actions == [(command.actions[0], False),
                       (command.actions[1], True),
                       (command.actions[2], False),
                       (command.actions[3], True)]

def test_Command_eq_same():
    assert command1 == command1

def test_Command_eq_equal():
    assert command1 == Command(command1.page, command1.actions)

def test_Command_eq_different_type():
    assert command1 != addCategory1
    assert command1 != None

def test_Command_eq_different_page():
    assert command1 != Command('Page A', command1.actions)

def test_Command_eq_different_actions():
    assert command1 != Command(command1.page, [addCategory1])

def test_Command_str():
    assert str(command1) == 'Page 1|+Category:Cat 1|-Category:Cat 2'

def test_Command_repr():
    assert eval(repr(command1)) == command1


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
    actual = action.apply(wikitext, ('Category', ['Category', 'Kategorie', 'K']))
    assert expected == actual

def test_AddCategoryAction_apply_detects_underscores():
    action = AddCategoryAction('My Test Category')
    wikitext = '[[Category:My_Test_Category]]'
    assert wikitext == action.apply(wikitext, ('Category', ['Category']))

def test_AddCategoryAction_apply_preserves_underscores():
    action1 = AddCategoryAction('Test Category 1')
    action2 = AddCategoryAction('Test_Category_2')
    action3 = AddCategoryAction('Test_Category 3')
    expected = '[[Category:Test Category 1]]\n[[Category:Test_Category_2]]\n[[Category:Test_Category 3]]'
    actual = ''
    for action in [action1, action2, action3]:
        actual = action.apply(actual, ('Category', ['Category']))
    assert expected == actual

def test_AddCategoryAction_summary():
    assert AddCategoryAction('Test').summary(('Kategorie', ['Kategorie', 'Category'])) == '+[[Kategorie:Test]]'

def test_AddCategoryAction_eq_same():
    assert addCategory1 == addCategory1

def test_AddCategoryAction_eq_equal():
    assert addCategory1 == AddCategoryAction(addCategory1.category)

def test_AddCategoryAction_eq_different_type():
    assert addCategory1 != RemoveCategoryAction(addCategory1.category)
    assert addCategory1 != None

def test_AddCategoryAction_eq_different_category():
    assert addCategory1 != addCategory3

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
    actual = action.apply(wikitext, ('Category', ['Category', 'Kategorie', 'K']))
    assert expected == actual

def test_RemoveCategoryAction_summary():
    assert RemoveCategoryAction('Test').summary(('Kategorie', ['Kategorie', 'Category'])) == '-[[Kategorie:Test]]'

def test_RemoveCategoryAction_eq_same():
    assert removeCategory2 == removeCategory2

def test_RemoveCategoryAction_eq_equal():
    assert removeCategory2 == RemoveCategoryAction(removeCategory2.category)

def test_RemoveCategoryAction_eq_different_type():
    assert removeCategory2 != AddCategoryAction(removeCategory2.category)
    assert removeCategory2 != None

def test_RemoveCategoryAction_eq_different_category():
    assert removeCategory2 != RemoveCategoryAction('Cat 4')

def test_RemoveCategoryAction_str():
    assert str(removeCategory2) == '-Category:Cat 2'

def test_RemoveCategoryAction_repr():
    assert eval(repr(removeCategory2)) == removeCategory2
