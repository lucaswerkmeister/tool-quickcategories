import datetime
from typing import cast

from action import AddCategoryAction, RemoveCategoryAction # NOQA “unused” import RemoveCategoryAction needed for eval(repr) test
from batch import NewBatch, OpenBatch, ClosedBatch
from batch_background_runs import BatchBackgroundRuns
from batch_command_records import BatchCommandRecords
from command import Command, CommandPlan, CommandEdit # NOQA “unused” imports CommandPlan, CommandEdit needed for eval(repr) test
from localuser import LocalUser # NOQA “unused” import LocalUser needed for eval(repr) test

from test_command import command1, command2, commandPlan1, commandEdit1
from test_localuser import localUser1, localUser2


newBatch1 = NewBatch([command1, command2], 'Test batch 1')


def test_NewBatch_cleanup():
    batch = NewBatch([Command('Page_1_from_URL', [AddCategoryAction('Category_from_URL')]),
                      Command('Page_2_from_URL', [AddCategoryAction('Category_from_URL')])],
                     '   test batch\t ')
    batch.cleanup()
    assert batch == NewBatch([Command('Page 1 from URL', [AddCategoryAction('Category from URL')]),
                              Command('Page 2 from URL', [AddCategoryAction('Category from URL')])],
                             'test batch')

def test_NewBatch_eq_same():
    assert newBatch1 == newBatch1

def test_NewBatch_eq_equal():
    assert newBatch1 == NewBatch(newBatch1.commands, newBatch1.title)

def test_NewBatch_eq_different_type():
    assert newBatch1 != command1

def test_NewBatch_eq_different_commands():
    assert newBatch1 != NewBatch([command1], newBatch1.title)

def test_NewBatch_eq_different_title():
    assert newBatch1 != NewBatch(newBatch1.commands, 'Other batch')

def test_NewBatch_str():
    assert str(newBatch1) == '''
# Test batch 1
Page 1|+Category:Cat 1|-Category:Cat 2
Page 2|+Category:Cat 3
'''.strip()

def test_NewBatch_repr():
    assert eval(repr(newBatch1)) == newBatch1


datetime1 = datetime.datetime(2019, 3, 17, 13, 23, 28, 251638, tzinfo=datetime.timezone.utc)
datetime2 = datetime.datetime(2019, 3, 17, 13, 48, 16, 844848, tzinfo=datetime.timezone.utc)
batchCommandRecords1 = cast(BatchCommandRecords, [commandPlan1, commandEdit1])
batchCommandRecords2 = cast(BatchCommandRecords, [commandPlan1])
batchBackgroundRuns1 = cast(BatchBackgroundRuns, [])
batchBackgroundRuns2 = cast(BatchBackgroundRuns, [((datetime.datetime.now(), ('Lucas Werkmeister', 6198807, 46618563)), None)])
openBatch1 = OpenBatch(5, localUser2, 'commons.wikimedia.org', 'Test batch 1', datetime1, datetime2, batchCommandRecords1, batchBackgroundRuns1)
closedBatch1 = ClosedBatch(5, localUser2, 'commons.wikimedia.org', 'Test batch 1', datetime1, datetime2, batchCommandRecords1, batchBackgroundRuns1)


def test_OpenBatch_eq_same():
    assert openBatch1 == openBatch1

def test_OpenBatch_eq_equal():
    assert openBatch1 == OpenBatch(5, localUser2, 'commons.wikimedia.org', 'Test batch 1', datetime1, datetime2, batchCommandRecords1, batchBackgroundRuns1)

def test_OpenBatch_eq_different_type():
    assert openBatch1 != newBatch1
    assert openBatch1 != closedBatch1

def test_OpenBatch_eq_different_id():
    assert openBatch1 != OpenBatch(6, openBatch1.local_user, openBatch1.domain, openBatch1.title, openBatch1.created, openBatch1.last_updated, openBatch1.command_records, openBatch1.background_runs)

def test_OpenBatch_eq_different_user():
    assert openBatch1 != OpenBatch(openBatch1.id, localUser1, openBatch1.domain, openBatch1.title, openBatch1.created, openBatch1.last_updated, openBatch1.command_records, openBatch1.background_runs)

def test_OpenBatch_eq_different_domain():
    assert openBatch1 != OpenBatch(openBatch1.id, openBatch1.local_user, 'meta.wikimedia.org', openBatch1.title, openBatch1.created, openBatch1.last_updated, openBatch1.command_records, openBatch1.background_runs)

def test_OpenBatch_eq_different_title():
    assert openBatch1 != OpenBatch(openBatch1.id, openBatch1.local_user, openBatch1.domain, 'Other batch', openBatch1.created, openBatch1.last_updated, openBatch1.command_records, openBatch1.background_runs)

def test_OpenBatch_eq_different_created():
    assert openBatch1 != OpenBatch(openBatch1.id, openBatch1.local_user, openBatch1.domain, openBatch1.title, datetime2, openBatch1.last_updated, openBatch1.command_records, openBatch1.background_runs)

def test_OpenBatch_eq_different_last_updated():
    assert openBatch1 != OpenBatch(openBatch1.id, openBatch1.local_user, openBatch1.domain, openBatch1.title, openBatch1.created, datetime1, openBatch1.command_records, openBatch1.background_runs)

def test_OpenBatch_eq_different_command_records():
    assert openBatch1 != OpenBatch(openBatch1.id, openBatch1.local_user, openBatch1.domain, openBatch1.title, openBatch1.created, openBatch1.last_updated, batchCommandRecords2, openBatch1.background_runs)

def test_OpenBatch_eq_different_background_runs():
    assert openBatch1 != OpenBatch(openBatch1.id, openBatch1.local_user, openBatch1.domain, openBatch1.title, openBatch1.created, openBatch1.last_updated, openBatch1.command_records, batchBackgroundRuns2)

def test_OpenBatch_str():
    assert str(openBatch1) == '''batch #5 on commons.wikimedia.org by Lucas Werkmeister'''

def test_OpenBatch_repr():
    assert eval(repr(openBatch1)) == openBatch1


def test_ClosedBatch_eq_same():
    assert closedBatch1 == closedBatch1

def test_ClosedBatch_eq_equal():
    assert closedBatch1 == ClosedBatch(5, localUser2, 'commons.wikimedia.org', 'Test batch 1', datetime1, datetime2, batchCommandRecords1, batchBackgroundRuns1)

def test_ClosedBatch_eq_different_type():
    assert closedBatch1 != newBatch1
    assert closedBatch1 != openBatch1

def test_ClosedBatch_eq_different_id():
    assert closedBatch1 != ClosedBatch(6, closedBatch1.local_user, closedBatch1.domain, closedBatch1.title, closedBatch1.created, closedBatch1.last_updated, closedBatch1.command_records, closedBatch1.background_runs)

def test_ClosedBatch_eq_different_user():
    assert closedBatch1 != ClosedBatch(closedBatch1.id, localUser1, closedBatch1.domain, closedBatch1.title, closedBatch1.created, closedBatch1.last_updated, closedBatch1.command_records, closedBatch1.background_runs)

def test_ClosedBatch_eq_different_domain():
    assert closedBatch1 != ClosedBatch(closedBatch1.id, closedBatch1.local_user, 'meta.wikimedia.org', closedBatch1.title, closedBatch1.created, closedBatch1.last_updated, closedBatch1.command_records, closedBatch1.background_runs)

def test_ClosedBatch_eq_different_title():
    assert closedBatch1 != ClosedBatch(closedBatch1.id, closedBatch1.local_user, closedBatch1.domain, 'Other batch', closedBatch1.created, closedBatch1.last_updated, closedBatch1.command_records, closedBatch1.background_runs)

def test_ClosedBatch_eq_different_created():
    assert closedBatch1 != ClosedBatch(closedBatch1.id, closedBatch1.local_user, closedBatch1.domain, closedBatch1.title, datetime2, closedBatch1.last_updated, closedBatch1.command_records, closedBatch1.background_runs)

def test_ClosedBatch_eq_different_last_updated():
    assert closedBatch1 != ClosedBatch(closedBatch1.id, closedBatch1.local_user, closedBatch1.domain, closedBatch1.title, closedBatch1.created, datetime1, closedBatch1.command_records, closedBatch1.background_runs)

def test_ClosedBatch_eq_different_command_records():
    assert closedBatch1 != ClosedBatch(closedBatch1.id, closedBatch1.local_user, closedBatch1.domain, closedBatch1.title, closedBatch1.created, closedBatch1.last_updated, batchCommandRecords2, closedBatch1.background_runs)

def test_ClosedBatch_eq_different_background_runs():
    assert closedBatch1 != ClosedBatch(closedBatch1.id, closedBatch1.local_user, closedBatch1.domain, closedBatch1.title, closedBatch1.created, closedBatch1.last_updated, closedBatch1.command_records, batchBackgroundRuns2)

def test_ClosedBatch_str():
    assert str(closedBatch1) == '''batch #5 on commons.wikimedia.org by Lucas Werkmeister'''

def test_ClosedBatch_repr():
    assert eval(repr(closedBatch1)) == closedBatch1
