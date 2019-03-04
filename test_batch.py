import pytest

from action import AddCategoryAction, RemoveCategoryAction
from batch import NewBatch, OpenBatch
from command import Command, CommandPlan, CommandEdit

from test_command import command1, command2, commandPlan1, commandEdit1


newBatch1 = NewBatch([command1, command2])


def test_NewBatch_eq_same():
    assert newBatch1 == newBatch1

def test_NewBatch_eq_equal():
    assert newBatch1 == NewBatch(newBatch1.commands)

def test_NewBatch_eq_different_type():
    assert newBatch1 != command1
    assert newBatch1 != None

def test_NewBatch_eq_different_commands():
    assert newBatch1 != NewBatch([command1])

def test_NewBatch_str():
    assert str(newBatch1) == '''
Page 1|+Category:Cat 1|-Category:Cat 2
Page 2|+Category:Cat 3
'''.strip()

def test_NewBatch_repr():
    assert eval(repr(newBatch1)) == newBatch1


openBatch1 = OpenBatch(5, 'commons.wikimedia.org', [commandPlan1, commandEdit1])


def test_OpenBatch_init():
    with pytest.raises(AssertionError):
        no_commands = OpenBatch(openBatch1.id, 'commons.wikimedia.org', [])
    with pytest.raises(AssertionError):
        no_plans = OpenBatch(openBatch1.id, 'commons.wikimedia.org', [commandEdit1])
    no_finishes = OpenBatch(openBatch1.id, 'commons.wikimedia.org', [commandPlan1])

def test_OpenBatch_eq_same():
    assert openBatch1 == openBatch1

def test_OpenBatch_eq_equal():
    assert openBatch1 == OpenBatch(5, 'commons.wikimedia.org', [commandPlan1, commandEdit1])

def test_OpenBatch_eq_different_type():
    assert openBatch1 != newBatch1
    assert openBatch1 != None

def test_OpenBatch_eq_different_id():
    assert openBatch1 != OpenBatch(6, openBatch1.domain, openBatch1.command_records)

def test_OpenBatch_eq_different_domain():
    assert openBatch1 != OpenBatch(openBatch1.id, 'meta.wikimedia.org', openBatch1.command_records)

def test_OpenBatch_eq_different_command_records():
    assert openBatch1 != OpenBatch(openBatch1.id, openBatch1.domain, [commandPlan1])

def test_OpenBatch_str():
    assert str(openBatch1) == '''
# commons.wikimedia.org
Page 1|+Category:Cat 1|-Category:Cat 2
# Page 2|+Category:Cat 3
'''.strip()

def test_OpenBatch_repr():
    assert eval(repr(openBatch1)) == openBatch1
