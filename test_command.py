import pytest

from action import AddCategoryAction, RemoveCategoryAction
from command import Command, CommandPlan, CommandEdit, CommandNoop

from test_action import addCategory1, removeCategory2, addCategory3


command1 = Command('Page 1', [addCategory1, removeCategory2])
command2 = Command('Page 2', [addCategory3])


def test_Command_apply():
    wikitext = 'Test page for the QuickCategories tool.\n[[Category:Already present cat]]\n[[Category:Removed cat]]\nBottom text'
    command = Command('Page title', [AddCategoryAction('Added cat'),
                                     AddCategoryAction('Already present cat'),
                                     RemoveCategoryAction('Removed cat'),
                                     RemoveCategoryAction('Not present cat')])
    new_wikitext, actions = command.apply(wikitext, ('Category', ['Category'], 'first-letter'))
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


commandPlan1 = CommandPlan(42, command1)


def test_CommandPlan_eq_same():
    assert commandPlan1 == commandPlan1

def test_CommandPlan_eq_equal():
    assert commandPlan1 == CommandPlan(commandPlan1.id, commandPlan1.command)

def test_CommandPlan_eq_different_id():
    assert commandPlan1 != CommandPlan(43, commandPlan1.command)

def test_CommandPlan_eq_different_command():
    assert commandPlan1 != CommandPlan(commandPlan1.id, command2)

def test_CommandPlan_str():
    assert str(commandPlan1) == str(command1)

def test_CommandPlan_repr():
    assert eval(repr(commandPlan1)) == commandPlan1


commandEdit1 = CommandEdit(42, command2, 1234, 1235)


def test_CommandEdit_init():
    with pytest.raises(AssertionError):
        CommandEdit(42, command1, base_revision=1235, revision=1234)

def test_CommandEdit_eq_same():
    assert commandEdit1 == commandEdit1

def test_CommandEdit_eq_equal():
    assert commandEdit1 == CommandEdit(42, command2, 1234, 1235)

def test_CommandEdit_eq_different_id():
    assert commandEdit1 != CommandEdit(43, commandEdit1.command, commandEdit1.base_revision, commandEdit1.revision)

def test_CommandEdit_eq_different_command():
    assert commandEdit1 != CommandEdit(commandEdit1.id, command1, commandEdit1.base_revision, commandEdit1.revision)

def test_CommandEdit_eq_different_base_revisoin():
    assert commandEdit1 != CommandEdit(commandEdit1.id, commandEdit1.command, 1233, commandEdit1.revision)

def test_CommandEdit_eq_different_revision():
    assert commandEdit1 != CommandEdit(commandEdit1.id, commandEdit1.command, commandEdit1.base_revision, 1236)

def test_CommandEdit_str():
    assert str(commandEdit1) == '# ' + str(command2)

def test_CommandEdit_repr():
    assert eval(repr(commandEdit1)) == commandEdit1


commandNoop1 = CommandNoop(42, command2, 1234)


def test_CommandNoop_eq_same():
    assert commandNoop1 == commandNoop1

def test_CommandNoop_eq_equal():
    assert commandNoop1 == CommandNoop(42, command2, 1234)

def test_CommandNoop_eq_different_id():
    assert commandNoop1 != CommandNoop(43, commandNoop1.command, commandNoop1.revision)

def test_CommandNoop_eq_different_command():
    assert commandNoop1 != CommandNoop(commandNoop1.id, command1, commandNoop1.revision)

def test_CommandNoop_eq_different_revision():
    assert commandNoop1 != CommandNoop(commandNoop1.id, commandNoop1.command, 1235)

def test_CommandNoop_str():
    assert str(commandNoop1) == '# ' + str(command2)

def test_CommandNoop_repr():
    assert eval(repr(commandNoop1)) == commandNoop1
