import datetime
import pytest  # type: ignore

from action import AddCategoryAction, RemoveCategoryAction
from command import Command, CommandPlan, CommandPending, CommandEdit, CommandNoop, CommandPageMissing, CommandTitleInvalid, CommandTitleInterwiki, CommandPageProtected, CommandEditConflict, CommandMaxlagExceeded, CommandBlocked, CommandWikiReadOnly
from page import Page

from test_action import addCategory1, removeCategory1, addCategory2
from test_page import page1, page2


command1 = Command(page1, [addCategory1, removeCategory1])
command2 = Command(page2, [addCategory2])


def test_Command_apply() -> None:
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

def test_Command_cleanup() -> None:
    command = Command(Page('Page_from_URL', True), [AddCategoryAction('Category_from_URL')])
    command.cleanup()
    assert command == Command(Page('Page from URL', True), [AddCategoryAction('Category from URL')])

def test_Command_actions_tpsv() -> None:
    assert command1.actions_tpsv() == '+Category:Cat 1|-Category:Cat 1'

def test_Command_str() -> None:
    assert str(command1) == 'Page 1|+Category:Cat 1|-Category:Cat 1'


commandPlan1 = CommandPlan(42, command1)


def test_CommandPlan_str() -> None:
    assert str(commandPlan1) == str(command1)


commandPending1 = CommandPending(42, command1)


def test_CommandPending_str() -> None:
    assert str(commandPending1) == str(command1)


commandEdit1 = CommandEdit(42, command2, 1234, 1235)


def test_CommandEdit_init() -> None:
    with pytest.raises(AssertionError):
        CommandEdit(42, command1, base_revision=1235, revision=1234)

def test_CommandEdit_str() -> None:
    assert str(commandEdit1) == '# ' + str(command2)


commandNoop1 = CommandNoop(42, command2, 1234)


def test_CommandNoop_str() -> None:
    assert str(commandNoop1) == '# ' + str(command2)


commandWithMissingPage = Command(Page('Page that definitely does not exist', True), command2.actions)
commandPageMissing1 = CommandPageMissing(42, commandWithMissingPage, '2019-03-11T23:26:02Z')


def test_CommandPageMissing_can_retry_immediately() -> None:
    assert not commandPageMissing1.can_retry_immediately()

def test_CommandPageMissing_can_retry_later() -> None:
    assert not commandPageMissing1.can_retry_later()

def test_CommandPageMissing_can_continue_batch() -> None:
    assert commandPageMissing1.can_continue_batch()

def test_CommandPageMissing_str() -> None:
    assert str(commandPageMissing1) == '# ' + str(commandWithMissingPage)


commandWithInvalidTitle = Command(Page('Category:', True), command2.actions)
commandTitleInvalid1 = CommandTitleInvalid(42, commandWithInvalidTitle, '2019-03-11T23:26:02Z')


def test_CommandTitleInvalid_can_retry_immediately() -> None:
    assert not commandTitleInvalid1.can_retry_immediately()

def test_CommandTitleInvalid_can_retry_later() -> None:
    assert not commandTitleInvalid1.can_retry_later()

def test_CommandTitleInvalid_can_continue_batch() -> None:
    assert commandTitleInvalid1.can_continue_batch()

def test_CommandTitleInvalid_str() -> None:
    assert str(commandTitleInvalid1) == '# ' + str(commandWithInvalidTitle)


commandWithInterwikiTitle = Command(Page('Commons: Sandbox', True), command2.actions)
commandTitleInterwiki1 = CommandTitleInterwiki(42, commandWithInterwikiTitle, '2022-02-15T18:46:30Z')


def test_CommandTitleInterwiki_can_retry_immediately() -> None:
    assert not commandTitleInterwiki1.can_retry_immediately()

def test_CommandTitleInterwiki_can_retry_later() -> None:
    assert not commandTitleInterwiki1.can_retry_later()

def test_CommandTitleInterwiki_can_continue_batch() -> None:
    assert commandTitleInterwiki1.can_continue_batch()

def test_CommandTitleInterwiki_str() -> None:
    assert str(commandTitleInterwiki1) == '# ' + str(commandWithInterwikiTitle)


commandWithProtectedPage = Command(Page('Main Page', True), command2.actions)
commandPageProtected1 = CommandPageProtected(42, commandWithProtectedPage, '2019-03-11T23:26:02Z')


def test_CommandPageProtected_can_retry_immediately() -> None:
    assert not commandPageProtected1.can_retry_immediately()

def test_CommandPageProtected_can_retry_later() -> None:
    assert not commandPageProtected1.can_retry_later()

def test_CommandPageProtected_can_continue_batch() -> None:
    assert commandPageProtected1.can_continue_batch()

def test_CommandPageProtected_str() -> None:
    assert str(commandPageProtected1) == '# ' + str(commandWithProtectedPage)


commandEditConflict1 = CommandEditConflict(42, command1)


def test_CommandEditConflict_can_retry_immediately() -> None:
    assert commandEditConflict1.can_retry_immediately()

def test_CommandEditConflict_can_retry_later() -> None:
    assert commandEditConflict1.can_retry_later()

def test_CommandEditConflict_can_continue_batch() -> None:
    assert commandEditConflict1.can_continue_batch()

def test_CommandEditConflict_str() -> None:
    assert str(commandEditConflict1) == '# ' + str(command1)


commandMaxlagExceeded1 = CommandMaxlagExceeded(42, command1, datetime.datetime(2019, 3, 16, 15, 24, 2, tzinfo=datetime.timezone.utc))


def test_CommandMaxlagExceeded_can_retry_immediately() -> None:
    assert not commandMaxlagExceeded1.can_retry_immediately()

def test_CommandMaxlagExceeded_can_retry_later() -> None:
    assert commandMaxlagExceeded1.can_retry_later()

def test_CommandMaxlagExceeded_can_continue_batch() -> None:
    assert commandMaxlagExceeded1.can_continue_batch() == commandMaxlagExceeded1.retry_after

def test_CommandMaxlagExceeded_str() -> None:
    assert str(commandMaxlagExceeded1) == '# ' + str(command1)


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


def test_CommandBlocked_can_retry_immediately() -> None:
    assert not commandBlocked1.can_retry_immediately()

def test_CommandBlocked_can_retry_later() -> None:
    assert commandBlocked1.can_retry_later()

def test_CommandBlocked_can_continue_batch() -> None:
    assert not commandBlocked1.can_continue_batch()

def test_CommandBlocked_str() -> None:
    assert str(commandBlocked1) == '# ' + str(command1)


commandWikiReadOnly1 = CommandWikiReadOnly(42, command1, 'maintenance', datetime.datetime(2019, 3, 16, 15, 24, 2, tzinfo=datetime.timezone.utc))
commandWikiReadOnly2 = CommandWikiReadOnly(42, command1, None, None)


def test_CommandWikiReadOnly_can_retry_immediately() -> None:
    assert not commandWikiReadOnly1.can_retry_immediately()

def test_CommandWikiReadOnly_can_retry_later() -> None:
    assert commandWikiReadOnly1.can_retry_later()

def test_CommandWikiReadOnly_can_continue_batch() -> None:
    assert commandWikiReadOnly1.can_continue_batch() == commandWikiReadOnly1.retry_after
    assert commandWikiReadOnly2.can_continue_batch() is False

def test_CommandWikiReadOnly_str() -> None:
    assert str(commandWikiReadOnly1) == '# ' + str(command1)
