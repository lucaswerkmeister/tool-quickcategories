from action import AddCategoryAction, RemoveCategoryAction
from batch import Batch
from command import Command

from test_command import command1, command2


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
