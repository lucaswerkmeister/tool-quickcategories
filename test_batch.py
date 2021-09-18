import datetime
from typing import cast

from action import AddCategoryAction, RemoveCategoryAction  # NOQA “unused” import RemoveCategoryAction needed for eval(repr) test
from batch import NewBatch, OpenBatch, ClosedBatch
from batch_background_runs import BatchBackgroundRuns
from batch_command_records import BatchCommandRecords
from command import Command, CommandPlan, CommandEdit  # NOQA “unused” imports CommandPlan, CommandEdit needed for eval(repr) test
from localuser import LocalUser  # NOQA “unused” import LocalUser needed for eval(repr) test
from page import Page

from test_command import command1, command2, commandPlan1, commandEdit1
from test_localuser import localUser2


newBatch1 = NewBatch([command1, command2], 'Test batch 1')


def test_NewBatch_cleanup() -> None:
    batch = NewBatch([Command(Page('Page_1_from_URL', True), [AddCategoryAction('Category_from_URL')]),
                      Command(Page('Page_2_from_URL', True), [AddCategoryAction('Category_from_URL')])],
                     '   test batch\t ')
    batch.cleanup()
    assert batch == NewBatch([Command(Page('Page 1 from URL', True), [AddCategoryAction('Category from URL')]),
                              Command(Page('Page 2 from URL', True), [AddCategoryAction('Category from URL')])],
                             'test batch')

def test_NewBatch_str() -> None:
    assert str(newBatch1) == '''
# Test batch 1
Page 1|+Category:Cat 1|-Category:Cat 1
!Page 2|+Category:Cat 2
'''.strip()


datetime1 = datetime.datetime(2019, 3, 17, 13, 23, 28, 251638, tzinfo=datetime.timezone.utc)
datetime2 = datetime.datetime(2019, 3, 17, 13, 48, 16, 844848, tzinfo=datetime.timezone.utc)
batchCommandRecords1 = cast(BatchCommandRecords, [commandPlan1, commandEdit1])
batchCommandRecords2 = cast(BatchCommandRecords, [commandPlan1])
batchBackgroundRuns1 = cast(BatchBackgroundRuns, [])
batchBackgroundRuns2 = cast(BatchBackgroundRuns, [((datetime.datetime.now(), ('Lucas Werkmeister', 6198807, 46618563)), None)])
openBatch1 = OpenBatch(5, localUser2, 'commons.wikimedia.org', 'Test batch 1', datetime1, datetime2, batchCommandRecords1, batchBackgroundRuns1)
closedBatch1 = ClosedBatch(5, localUser2, 'commons.wikimedia.org', 'Test batch 1', datetime1, datetime2, batchCommandRecords1, batchBackgroundRuns1)


def test_OpenBatch_str() -> None:
    assert str(openBatch1) == '''batch #5 on commons.wikimedia.org by Lucas Werkmeister'''


def test_ClosedBatch_str() -> None:
    assert str(closedBatch1) == '''batch #5 on commons.wikimedia.org by Lucas Werkmeister'''
