from action import AddCategoryAction, RemoveCategoryAction
from command import Command

from test_action import addCategory1, removeCategory2, addCategory3


command1 = Command('Page 1', [addCategory1, removeCategory2])
command2 = Command('Page 2', [addCategory3])


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
