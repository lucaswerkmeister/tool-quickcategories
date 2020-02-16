import datetime
import pytest  # type: ignore

from action import AddCategoryAction, RemoveCategoryAction
from command import Command, CommandPlan, CommandPending, CommandEdit, CommandNoop, CommandPageMissing, CommandTitleInvalid, CommandPageProtected, CommandEditConflict, CommandMaxlagExceeded, CommandBlocked, CommandWikiReadOnly
from page import Page

from test_action import addCategory1, removeCategory1, addCategory2
from test_page import page1, page2


command1 = Command(page1, [addCategory1, removeCategory1])
command2 = Command(page2, [addCategory2])


def test_Command_apply():
    wikitext = 'Test page for the QuickCategories tool.\n[[Category:Already present cat]]\n[[Category:Removed cat]]\nBottom text'
    command = Command(Page('Page title', True), [AddCategoryAction('Added cat'),
                                                 AddCategoryAction('Already present cat'),
                                                 RemoveCategoryAction('Removed cat'),
                                                 RemoveCategoryAction('Not present cat')])
    new_wikitext, actions = command.apply(wikitext, ('Category', ['Category'], 'first-letter'))
    assert new_wikitext == 'Test page for the QuickCategories tool.\n[[Category:Already present cat]]\n[[Category:Added cat]]\nBottom text'
    assert actions == [(command.actions[0], False),
                       (command.actions[1], True),
                       (command.actions[2], False),
                       (command.actions[3], True)]

def test_Command_cleanup():
    command = Command(Page('Page_from_URL', True), [AddCategoryAction('Category_from_URL')])
    command.cleanup()
    assert command == Command(Page('Page from URL', True), [AddCategoryAction('Category from URL')])

def test_Command_actions_tpsv():
    assert command1.actions_tpsv() == '+Category:Cat 1|-Category:Cat 1'

def test_Command_eq_same():
    assert command1 == command1

def test_Command_eq_equal():
    assert command1 == Command(command1.page, command1.actions)

def test_Command_eq_different_type():
    assert command1 != addCategory1

def test_Command_eq_different_page():
    assert command1 != Command(Page('Page A', True), command1.actions)
    assert command1 != Command(Page('Page_1', True), command1.actions)
    assert command1 != Command(Page('Page 1', False), command1.actions)

def test_Command_eq_different_actions():
    assert command1 != Command(command1.page, [addCategory1])

def test_Command_str():
    assert str(command1) == 'Page 1|+Category:Cat 1|-Category:Cat 1'

def test_Command_repr():
    assert eval(repr(command1)) == command1


commandPlan1 = CommandPlan(42, command1)


def test_CommandPlan_eq_same():
    assert commandPlan1 == commandPlan1

def test_CommandPlan_eq_equal():
    assert commandPlan1 == CommandPlan(commandPlan1.id, commandPlan1.command)

def test_CommandPlan_eq_different_type():
    assert commandPlan1 != commandPending1

def test_CommandPlan_eq_different_id():
    assert commandPlan1 != CommandPlan(43, commandPlan1.command)

def test_CommandPlan_eq_different_command():
    assert commandPlan1 != CommandPlan(commandPlan1.id, command2)

def test_CommandPlan_str():
    assert str(commandPlan1) == str(command1)

def test_CommandPlan_repr():
    assert eval(repr(commandPlan1)) == commandPlan1


commandPending1 = CommandPending(42, command1)


def test_CommandPending_eq_same():
    assert commandPending1 == commandPending1

def test_CommandPending_eq_equal():
    assert commandPending1 == CommandPending(commandPending1.id, commandPending1.command)

def test_CommandPending_eq_different_type():
    assert commandPending1 != commandPlan1

def test_CommandPending_eq_different_id():
    assert commandPending1 != CommandPending(43, commandPending1.command)

def test_CommandPending_eq_different_command():
    assert commandPending1 != CommandPending(commandPending1.id, command2)

def test_CommandPending_str():
    assert str(commandPending1) == str(command1)

def test_CommandPending_repr():
    assert eval(repr(commandPending1)) == commandPending1


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


commandWithMissingPage = Command(Page('Page that definitely does not exist', True), command2.actions)
commandPageMissing1 = CommandPageMissing(42, commandWithMissingPage, '2019-03-11T23:26:02Z')


def test_CommandPageMissing_can_retry_immediately():
    assert not commandPageMissing1.can_retry_immediately()

def test_CommandPageMissing_can_retry_later():
    assert not commandPageMissing1.can_retry_later()

def test_CommandPageMissing_can_continue_batch():
    assert commandPageMissing1.can_continue_batch()

def test_CommandPageMissing_eq_same():
    assert commandPageMissing1 == commandPageMissing1

def test_CommandPageMissing_eq_equal():
    assert commandPageMissing1 == CommandPageMissing(42, commandWithMissingPage, '2019-03-11T23:26:02Z')

def test_CommandPageMissing_eq_different_type():
    assert commandPageMissing1 != commandPageProtected1
    assert commandPageMissing1 != commandTitleInvalid1

def test_CommandPageMissing_eq_different_id():
    assert commandPageMissing1 != CommandPageMissing(43, commandPageMissing1.command, commandPageMissing1.curtimestamp)

def test_CommandPageMissing_eq_different_command():
    assert commandPageMissing1 != CommandPageMissing(commandPageMissing1.id, command2, commandPageMissing1.curtimestamp)

def test_CommandPageMissing_eq_different_curtimestamp():
    assert commandPageMissing1 != CommandPageMissing(commandPageMissing1.id, commandPageMissing1.command, '2019-03-11T23:28:12Z')

def test_CommandPageMissing_str():
    assert str(commandPageMissing1) == '# ' + str(commandWithMissingPage)

def test_CommandPageMissing_repr():
    assert eval(repr(commandPageMissing1)) == commandPageMissing1


commandWithInvalidTitle = Command(Page('Category:', True), command2.actions)
commandTitleInvalid1 = CommandTitleInvalid(42, commandWithInvalidTitle, '2019-03-11T23:26:02Z')


def test_CommandTitleInvalid_can_retry_immediately():
    assert not commandTitleInvalid1.can_retry_immediately()

def test_CommandTitleInvalid_can_retry_later():
    assert not commandTitleInvalid1.can_retry_later()

def test_CommandTitleInvalid_can_continue_batch():
    assert commandTitleInvalid1.can_continue_batch()

def test_CommandTitleInvalid_eq_same():
    assert commandTitleInvalid1 == commandTitleInvalid1

def test_CommandTitleInvalid_eq_equal():
    assert commandTitleInvalid1 == CommandTitleInvalid(42, commandWithInvalidTitle, '2019-03-11T23:26:02Z')

def test_CommandTitleInvalid_eq_different_type():
    assert commandTitleInvalid1 != commandPageProtected1
    assert commandTitleInvalid1 != commandPageMissing1

def test_CommandTitleInvalid_eq_different_id():
    assert commandTitleInvalid1 != CommandTitleInvalid(43, commandTitleInvalid1.command, commandTitleInvalid1.curtimestamp)

def test_CommandTitleInvalid_eq_different_command():
    assert commandTitleInvalid1 != CommandTitleInvalid(commandTitleInvalid1.id, command2, commandTitleInvalid1.curtimestamp)

def test_CommandTitleInvalid_eq_different_curtimestamp():
    assert commandTitleInvalid1 != CommandTitleInvalid(commandTitleInvalid1.id, commandTitleInvalid1.command, '2019-03-11T23:28:12Z')

def test_CommandTitleInvalid_str():
    assert str(commandTitleInvalid1) == '# ' + str(commandWithInvalidTitle)

def test_CommandTitleInvalid_repr():
    assert eval(repr(commandTitleInvalid1)) == commandTitleInvalid1


commandWithProtectedPage = Command(Page('Main Page', True), command2.actions)
commandPageProtected1 = CommandPageProtected(42, commandWithProtectedPage, '2019-03-11T23:26:02Z')


def test_CommandPageProtected_can_retry_immediately():
    assert not commandPageProtected1.can_retry_immediately()

def test_CommandPageProtected_can_retry_later():
    assert not commandPageProtected1.can_retry_later()

def test_CommandPageProtected_can_continue_batch():
    assert commandPageProtected1.can_continue_batch()

def test_CommandPageProtected_eq_same():
    assert commandPageProtected1 == commandPageProtected1

def test_CommandPageProtected_eq_equal():
    assert commandPageProtected1 == CommandPageProtected(42, commandWithProtectedPage, '2019-03-11T23:26:02Z')

def test_CommandPageProtected_eq_different_type():
    assert commandPageProtected1 != commandPageMissing1

def test_CommandPageProtected_eq_different_id():
    assert commandPageProtected1 != CommandPageProtected(43, commandPageProtected1.command, commandPageProtected1.curtimestamp)

def test_CommandPageProtected_eq_different_command():
    assert commandPageProtected1 != CommandPageProtected(commandPageProtected1.id, command2, commandPageProtected1.curtimestamp)

def test_CommandPageProtected_eq_different_curtimestamp():
    assert commandPageProtected1 != CommandPageProtected(commandPageProtected1.id, commandPageProtected1.command, '2019-03-11T23:28:12Z')

def test_CommandPageProtected_str():
    assert str(commandPageProtected1) == '# ' + str(commandWithProtectedPage)

def test_CommandPageProtected_repr():
    assert eval(repr(commandPageProtected1)) == commandPageProtected1


commandEditConflict1 = CommandEditConflict(42, command1)


def test_CommandEditConflict_can_retry_immediately():
    assert commandEditConflict1.can_retry_immediately()

def test_CommandEditConflict_can_retry_later():
    assert commandEditConflict1.can_retry_later()

def test_CommandEditConflict_can_continue_batch():
    assert commandEditConflict1.can_continue_batch()

def test_CommandEditConflict_eq_same():
    assert commandEditConflict1 == commandEditConflict1

def test_CommandEditConflict_eq_equal():
    assert commandEditConflict1 == CommandEditConflict(42, command1)

def test_CommandEditConflict_eq_different_id():
    assert commandEditConflict1 != CommandEditConflict(43, commandEditConflict1.command)

def test_CommandEditConflict_eq_different_command():
    assert commandEditConflict1 != CommandEditConflict(commandEditConflict1.id, command2)

def test_CommandEditConflict_str():
    assert str(commandEditConflict1) == '# ' + str(command1)

def test_CommandEditConflict_repr():
    assert eval(repr(commandEditConflict1)) == commandEditConflict1


commandMaxlagExceeded1 = CommandMaxlagExceeded(42, command1, datetime.datetime(2019, 3, 16, 15, 24, 2, tzinfo=datetime.timezone.utc))


def test_CommandMaxlagExceeded_can_retry_immediately():
    assert not commandMaxlagExceeded1.can_retry_immediately()

def test_CommandMaxlagExceeded_can_retry_later():
    assert commandMaxlagExceeded1.can_retry_later()

def test_CommandMaxlagExceeded_can_continue_batch():
    assert commandMaxlagExceeded1.can_continue_batch() == commandMaxlagExceeded1.retry_after

def test_CommandMaxlagExceeded_eq_same():
    assert commandMaxlagExceeded1 == commandMaxlagExceeded1

def test_CommandMaxlagExceeded_eq_equal():
    assert commandMaxlagExceeded1 == CommandMaxlagExceeded(42, command1, datetime.datetime(2019, 3, 16, 15, 24, 2, tzinfo=datetime.timezone.utc))

def test_CommandMaxlagExceeded_eq_different_id():
    assert commandMaxlagExceeded1 != CommandMaxlagExceeded(43, commandMaxlagExceeded1.command, commandMaxlagExceeded1.retry_after)

def test_CommandMaxlagExceeded_eq_different_command():
    assert commandMaxlagExceeded1 != CommandMaxlagExceeded(commandMaxlagExceeded1.id, command2, commandMaxlagExceeded1.retry_after)

def test_CommandMaxlagExceeded_eq_different_retry_after():
    assert commandMaxlagExceeded1 != CommandMaxlagExceeded(commandMaxlagExceeded1.id, commandMaxlagExceeded1.command, datetime.datetime(2019, 3, 16, 15, 24, 2, tzinfo=datetime.timezone.max))

def test_CommandMaxlagExceeded_str():
    assert str(commandMaxlagExceeded1) == '# ' + str(command1)

def test_CommandMaxlagExceeded_repr():
    assert eval(repr(commandMaxlagExceeded1)) == commandMaxlagExceeded1


blockinfo = {
    'blockedby': 'Lucas Werkmeister',
    'blockedbyid': 1,
    'blockedtimestamp': '2019-03-16T17:44:22Z',
    'blockexpiry': 'indefinite',
    'blockid': 1,
    'blockpartial': False,
    'blockreason': 'my custom reason',
}
commandBlocked1 = CommandBlocked(42, command1, False, blockinfo)
commandBlocked2 = CommandBlocked(42, command1, False, None)


def test_CommandBlocked_can_retry_immediately():
    assert not commandBlocked1.can_retry_immediately()

def test_CommandBlocked_can_retry_later():
    assert commandBlocked1.can_retry_later()

def test_CommandBlocked_can_continue_batch():
    assert not commandBlocked1.can_continue_batch()

def test_CommandBlocked_eq_same():
    assert commandBlocked1 == commandBlocked1

def test_CommandBlocked_eq_equal():
    assert commandBlocked1 == CommandBlocked(42, command1, False, blockinfo)

def test_CommandBlocked_eq_different_id():
    assert commandBlocked1 != CommandBlocked(43, commandBlocked1.command, commandBlocked1.auto, commandBlocked1.blockinfo)

def test_CommandBlocked_eq_different_command():
    assert commandBlocked1 != CommandBlocked(commandBlocked1.id, command2, commandBlocked1.auto, commandBlocked1.blockinfo)

def test_CommandBlocked_eq_different_auto():
    assert commandBlocked1 != CommandBlocked(commandBlocked1.id, commandBlocked1.command, True, blockinfo)

def test_CommandBlocked_eq_different_blockinfo():
    assert commandBlocked1 != CommandBlocked(commandBlocked1.id, commandBlocked1.command, commandBlocked1.auto, None)

def test_CommandBlocked_str():
    assert str(commandBlocked1) == '# ' + str(command1)

def test_CommandBlocked_repr():
    assert eval(repr(commandBlocked1)) == commandBlocked1


commandWikiReadOnly1 = CommandWikiReadOnly(42, command1, 'maintenance', datetime.datetime(2019, 3, 16, 15, 24, 2, tzinfo=datetime.timezone.utc))
commandWikiReadOnly2 = CommandWikiReadOnly(42, command1, None, None)


def test_CommandWikiReadOnly_can_retry_immediately():
    assert not commandWikiReadOnly1.can_retry_immediately()

def test_CommandWikiReadOnly_can_retry_later():
    assert commandWikiReadOnly1.can_retry_later()

def test_CommandWikiReadOnly_can_continue_batch():
    assert commandWikiReadOnly1.can_continue_batch() == commandWikiReadOnly1.retry_after
    assert commandWikiReadOnly2.can_continue_batch() is False

def test_CommandWikiReadOnly_eq_same():
    assert commandWikiReadOnly1 == commandWikiReadOnly1

def test_CommandWikiReadOnly_eq_equal():
    assert commandWikiReadOnly1 == CommandWikiReadOnly(42, command1, 'maintenance', datetime.datetime(2019, 3, 16, 15, 24, 2, tzinfo=datetime.timezone.utc))

def test_CommandWikiReadOnly_eq_different_id():
    assert commandWikiReadOnly1 != CommandWikiReadOnly(43, commandWikiReadOnly1.command, commandWikiReadOnly1.reason, commandWikiReadOnly1.retry_after)

def test_CommandWikiReadOnly_eq_different_command():
    assert commandWikiReadOnly1 != CommandWikiReadOnly(commandWikiReadOnly1.id, command2, commandWikiReadOnly1.reason, commandWikiReadOnly1.retry_after)

def test_CommandWikiReadOnly_eq_different_reason():
    assert commandWikiReadOnly1 != CommandWikiReadOnly(commandWikiReadOnly1.id, commandWikiReadOnly1.command, None, commandWikiReadOnly1.retry_after)

def test_CommandWikiReadOnly_eq_different_retry_after():
    assert commandWikiReadOnly1 != CommandWikiReadOnly(commandWikiReadOnly1.id, commandWikiReadOnly1.command, commandWikiReadOnly1.reason, None)

def test_CommandWikiReadOnly_str():
    assert str(commandWikiReadOnly1) == '# ' + str(command1)

def test_CommandWikiReadOnly_repr():
    assert eval(repr(commandWikiReadOnly1)) == commandWikiReadOnly1
