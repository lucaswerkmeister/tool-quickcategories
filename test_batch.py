import datetime

from action import AddCategoryAction, RemoveCategoryAction # NOQA “unused” import RemoveCategoryAction needed for eval(repr) test
from batch import NewBatch, OpenBatch, ClosedBatch, BatchCommandRecordsList
from command import Command, CommandPlan, CommandEdit # NOQA “unused” imports CommandPlan, CommandEdit needed for eval(repr) test

from test_command import command1, command2, commandPlan1, commandEdit1


newBatch1 = NewBatch([command1, command2])


def test_NewBatch_cleanup():
    batch = NewBatch([Command('Page_1_from_URL', [AddCategoryAction('Category_from_URL')]),
                      Command('Page_2_from_URL', [AddCategoryAction('Category_from_URL')])])
    batch.cleanup()
    assert batch == NewBatch([Command('Page 1 from URL', [AddCategoryAction('Category from URL')]),
                              Command('Page 2 from URL', [AddCategoryAction('Category from URL')])])

def test_NewBatch_eq_same():
    assert newBatch1 == newBatch1

def test_NewBatch_eq_equal():
    assert newBatch1 == NewBatch(newBatch1.commands)

def test_NewBatch_eq_different_type():
    assert newBatch1 != command1

def test_NewBatch_eq_different_commands():
    assert newBatch1 != NewBatch([command1])

def test_NewBatch_str():
    assert str(newBatch1) == '''
Page 1|+Category:Cat 1|-Category:Cat 2
Page 2|+Category:Cat 3
'''.strip()

def test_NewBatch_repr():
    assert eval(repr(newBatch1)) == newBatch1


datetime1 = datetime.datetime(2019, 3, 17, 13, 23, 28, 251638, tzinfo=datetime.timezone.utc)
datetime2 = datetime.datetime(2019, 3, 17, 13, 48, 16, 844848, tzinfo=datetime.timezone.utc)
batchCommandRecords1 = BatchCommandRecordsList([commandPlan1, commandEdit1])
openBatch1 = OpenBatch(5, 'Lucas Werkmeister', 6198807, 46054761, 'commons.wikimedia.org', datetime1, datetime2, batchCommandRecords1)
closedBatch1 = ClosedBatch(5, 'Lucas Werkmeister', 6198807, 46054761, 'commons.wikimedia.org', datetime1, datetime2, batchCommandRecords1)


def test_OpenBatch_eq_same():
    assert openBatch1 == openBatch1

def test_OpenBatch_eq_equal():
    assert openBatch1 == OpenBatch(5, 'Lucas Werkmeister', 6198807, 46054761, 'commons.wikimedia.org', datetime1, datetime2, batchCommandRecords1)

def test_OpenBatch_eq_different_type():
    assert openBatch1 != newBatch1
    assert openBatch1 != closedBatch1

def test_OpenBatch_eq_different_id():
    assert openBatch1 != OpenBatch(6, openBatch1.user_name, openBatch1.local_user_id, openBatch1.global_user_id, openBatch1.domain, openBatch1.created, openBatch1.last_updated, openBatch1.command_records)

def test_OpenBatch_eq_different_user_name():
    assert openBatch1 != OpenBatch(openBatch1.id, 'TweetsFactsAndQueries', openBatch1.local_user_id, openBatch1.global_user_id, openBatch1.domain, openBatch1.created, openBatch1.last_updated, openBatch1.command_records)

def test_OpenBatch_eq_different_local_user_id():
    assert openBatch1 != OpenBatch(openBatch1.id, openBatch1.user_name, 6020327, openBatch1.global_user_id, openBatch1.domain, openBatch1.created, openBatch1.last_updated, openBatch1.command_records)

def test_OpenBatch_eq_different_global_user_id():
    assert openBatch1 != OpenBatch(openBatch1.id, openBatch1.user_name, openBatch1.local_user_id, 46618563, openBatch1.domain, openBatch1.created, openBatch1.last_updated, openBatch1.command_records)

def test_OpenBatch_eq_different_domain():
    assert openBatch1 != OpenBatch(openBatch1.id, openBatch1.user_name, openBatch1.local_user_id, openBatch1.global_user_id, 'meta.wikimedia.org', openBatch1.created, openBatch1.last_updated, openBatch1.command_records)

def test_OpenBatch_eq_different_created():
    assert openBatch1 != OpenBatch(openBatch1.id, openBatch1.user_name, openBatch1.local_user_id, openBatch1.global_user_id, openBatch1.domain, datetime2, openBatch1.last_updated, openBatch1.command_records)

def test_OpenBatch_eq_different_last_updated():
    assert openBatch1 != OpenBatch(openBatch1.id, openBatch1.user_name, openBatch1.local_user_id, openBatch1.global_user_id, openBatch1.domain, openBatch1.created, datetime1, openBatch1.command_records)

def test_OpenBatch_eq_different_command_records():
    assert openBatch1 != OpenBatch(openBatch1.id, openBatch1.user_name, openBatch1.local_user_id, openBatch1.global_user_id, openBatch1.domain, openBatch1.created, openBatch1.last_updated, BatchCommandRecordsList([commandPlan1]))

def test_OpenBatch_str():
    assert str(openBatch1) == '''batch #5 on commons.wikimedia.org by Lucas Werkmeister'''

def test_OpenBatch_repr():
    assert eval(repr(openBatch1)) == openBatch1


def test_ClosedBatch_eq_same():
    assert closedBatch1 == closedBatch1

def test_ClosedBatch_eq_equal():
    assert closedBatch1 == ClosedBatch(5, 'Lucas Werkmeister', 6198807, 46054761, 'commons.wikimedia.org', datetime1, datetime2, batchCommandRecords1)

def test_ClosedBatch_eq_different_type():
    assert closedBatch1 != newBatch1
    assert closedBatch1 != openBatch1

def test_ClosedBatch_eq_different_id():
    assert closedBatch1 != ClosedBatch(6, closedBatch1.user_name, closedBatch1.local_user_id, closedBatch1.global_user_id, closedBatch1.domain, closedBatch1.created, closedBatch1.last_updated, closedBatch1.command_records)

def test_ClosedBatch_eq_different_user_name():
    assert closedBatch1 != ClosedBatch(closedBatch1.id, 'TweetsFactsAndQueries', closedBatch1.local_user_id, closedBatch1.global_user_id, closedBatch1.domain, closedBatch1.created, closedBatch1.last_updated, closedBatch1.command_records)

def test_ClosedBatch_eq_different_local_user_id():
    assert closedBatch1 != ClosedBatch(closedBatch1.id, closedBatch1.user_name, 6020327, closedBatch1.global_user_id, closedBatch1.domain, closedBatch1.created, closedBatch1.last_updated, closedBatch1.command_records)

def test_ClosedBatch_eq_different_global_user_id():
    assert closedBatch1 != ClosedBatch(closedBatch1.id, closedBatch1.user_name, closedBatch1.local_user_id, 46618563, closedBatch1.domain, closedBatch1.created, closedBatch1.last_updated, closedBatch1.command_records)

def test_ClosedBatch_eq_different_domain():
    assert closedBatch1 != ClosedBatch(closedBatch1.id, closedBatch1.user_name, closedBatch1.local_user_id, closedBatch1.global_user_id, 'meta.wikimedia.org', closedBatch1.created, closedBatch1.last_updated, closedBatch1.command_records)

def test_ClosedBatch_eq_different_created():
    assert closedBatch1 != ClosedBatch(closedBatch1.id, closedBatch1.user_name, closedBatch1.local_user_id, closedBatch1.global_user_id, closedBatch1.domain, datetime2, closedBatch1.last_updated, closedBatch1.command_records)

def test_ClosedBatch_eq_different_last_updated():
    assert closedBatch1 != ClosedBatch(closedBatch1.id, closedBatch1.user_name, closedBatch1.local_user_id, closedBatch1.global_user_id, closedBatch1.domain, closedBatch1.created, datetime1, closedBatch1.command_records)

def test_ClosedBatch_eq_different_command_records():
    assert closedBatch1 != ClosedBatch(closedBatch1.id, closedBatch1.user_name, closedBatch1.local_user_id, closedBatch1.global_user_id, closedBatch1.domain, closedBatch1.created, closedBatch1.last_updated, BatchCommandRecordsList([commandPlan1]))

def test_ClosedBatch_str():
    assert str(closedBatch1) == '''batch #5 on commons.wikimedia.org by Lucas Werkmeister'''

def test_ClosedBatch_repr():
    assert eval(repr(closedBatch1)) == closedBatch1
