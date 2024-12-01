import datetime
import mwapi  # type: ignore
import os
import pytest
from typing import Any, Optional

from action import Action, AddCategoryAction, RemoveCategoryAction
from command import Command, CommandPending, CommandEdit, CommandNoop, CommandPageMissing, CommandTitleInvalid, CommandTitleInterwiki, CommandPageProtected, CommandPageBadContentFormat, CommandEditConflict, CommandMaxlagExceeded, CommandBlocked, CommandWikiReadOnly
from page import Page
from runner import Runner
from store import WatchlistParam

from test_utils import FakeSession

def test_resolve_pages_and_run_commands() -> None:
    session = logged_in_session('https://test.wikipedia.org')

    suffix = ''
    if 'CI_JOB_NUMBER' in os.environ:
        suffix = '/' + os.environ['CI_JOB_NUMBER']

    title_A = 'QuickCategories CI Test' + suffix
    title_B = 'QuickCategories CI Test Redirect' + suffix
    title_B2 = 'QuickCategories CI Test Redirect Target' + suffix
    title_C = 'QuickCategories CI Test Other Redirect' + suffix
    title_C2 = 'QuickCategories CI Test Other Redirect Target' + suffix

    actions: list[Action] = [AddCategoryAction('Added cat'),
                             AddCategoryAction('Already present cat'),
                             RemoveCategoryAction('Removed cat'),
                             RemoveCategoryAction('Not present cat')]
    command_A = Command(Page(title_A, True), actions)
    command_B = Command(Page(title_B, True), actions)
    command_C = Command(Page(title_C, False), actions)
    runner = Runner(session, WatchlistParam.preferences, summary_batch_title='QuickCategories CI test')
    base_A = set_page_wikitext('setup',
                               title_A,
                               'Test page for the QuickCategories tool.\n[[Category:Already present cat]]\n[[Category:Removed cat]]\nBottom text',
                               runner,
                               watchlist_param=WatchlistParam.unwatch)
    base_B = set_page_wikitext('setup',  # NOQA: F841 (unused)
                               title_B,
                               '#REDIRECT [[' + title_B2 + ']]\n\n[[Category:Unchanged cat]]',
                               runner,
                               watchlist_param=WatchlistParam.unwatch)
    base_B2 = set_page_wikitext('setup',
                                title_B2,
                                'Test page for the QuickCategories tool.\n[[Category:Already present cat]]\n[[Category:Removed cat]]\nBottom text',
                                runner,
                                watchlist_param=WatchlistParam.unwatch)
    base_C = set_page_wikitext('setup',
                               title_C,
                               '#REDIRECT [[' + title_C2 + ']]\n\n[[Category:Already present cat]]\n[[Category:Removed cat]]',
                               runner,
                               watchlist_param=WatchlistParam.unwatch)
    base_C2 = set_page_wikitext('setup',  # NOQA: F841 (unused)
                                title_C2,
                                'Test page for the QuickCategories tool.\n[[Category:Unchanged cat]]\nBottom text',
                                runner,
                                watchlist_param=WatchlistParam.unwatch)

    runner.resolve_pages([command_A.page,
                          command_B.page,
                          command_C.page])
    runner.watchlist_param = WatchlistParam.preferences
    edit_A = runner.run_command(CommandPending(0, command_A))
    edit_B = runner.run_command(CommandPending(0, command_B))
    runner.watchlist_param = WatchlistParam.watch
    edit_C = runner.run_command(CommandPending(0, command_C))

    assert isinstance(edit_A, CommandEdit)
    assert edit_A.base_revision == base_A
    assert command_A.page.resolution is None

    assert isinstance(edit_B, CommandEdit)
    assert edit_B.base_revision == base_B2
    assert command_B.page.resolution is None

    assert isinstance(edit_C, CommandEdit)
    assert edit_C.base_revision == base_C
    assert command_C.page.resolution is None

    revision_A = get_page_revision(title_A, runner)
    revision_B = get_page_revision(title_B, runner)
    revision_B2 = get_page_revision(title_B2, runner)
    revision_C = get_page_revision(title_C, runner)
    revision_C2 = get_page_revision(title_C2, runner)

    expected_comment = '+[[Category:Added cat]], (+[[Category:Already present cat]]), -[[Category:Removed cat]], (-[[Category:Not present cat]]); QuickCategories CI test'
    for revision in [revision_A, revision_B2, revision_C]:
        assert revision['comment'] == expected_comment
        assert not revision['minor']

    expected_page_content = 'Test page for the QuickCategories tool.\n[[Category:Already present cat]]\n[[Category:Added cat]]\nBottom text'
    for revision in [revision_A, revision_B2]:
        assert revision['slots']['main']['content'] == expected_page_content
    expected_redirect_content = '#REDIRECT [[' + title_C2 + ']]\n\n[[Category:Already present cat]]\n[[Category:Added cat]]'
    assert revision_C['slots']['main']['content'] == expected_redirect_content

    assert revision_B['slots']['main']['content'] == '#REDIRECT [[' + title_B2 + ']]\n\n[[Category:Unchanged cat]]'
    assert revision_C2['slots']['main']['content'] == 'Test page for the QuickCategories tool.\n[[Category:Unchanged cat]]\nBottom text'

    watchlist = session.get(action='query',
                            list='watchlistraw',
                            wrfromtitle='QuickCategories CI Test',
                            wrtotitle='QuickCategories CI Tesu',
                            wrlimit='max')['watchlistraw']
    # the test assumes that the “Add pages and files I edit to my watchlist” preference is *not* set,
    # so the only page in the watchlist should be title_C
    # (but another test with a different suffix may be running concurrently)
    relevant_titles = {title_A, title_B, title_B2, title_C, title_C2}
    relevant_watched_titles = [page['title'] for page in watchlist
                               if page['title'] in relevant_titles]
    assert relevant_watched_titles == [title_C]

    set_page_wikitext('teardown', title_A, 'Test page for the QuickCategories tool.', runner)
    set_page_wikitext('teardown', title_B, '#REDIRECT [[' + title_B2 + ']]', runner)
    set_page_wikitext('teardown', title_B2, 'Test page for the QuickCategories tool.', runner)
    set_page_wikitext('teardown', title_C, '#REDIRECT [[' + title_C2 + ']]', runner)
    set_page_wikitext('teardown', title_C2, 'Test page for the QuickCategories tool.', runner)

def test_resolve_pages_and_run_commands_test2wiki() -> None:
    """test2wiki has ProofreadPage installed, so we can test Wikisource support here."""
    session = logged_in_session('https://test2.wikipedia.org')

    suffix = ''
    if 'CI_JOB_NUMBER' in os.environ:
        suffix = ' ' + os.environ['CI_JOB_NUMBER']
    title = 'Index:QuickCategories CI Test' + suffix

    actions: list[Action] = [AddCategoryAction('Added cat')]
    command = Command(Page(title, True), actions)
    runner = Runner(session, WatchlistParam.preferences, summary_batch_title='QuickCategories CI test')
    base_content = '''
{{:MediaWiki:Proofreadpage_index_template
|Type=book
|Title=%s
|Language=en
|Volume=
|Author=
|Translator=
|Editor=
|Illustrator=
|School=
|Publisher=
|Address=
|Year=
|Key=
|wikidata_item=
|ISBN=
|OCLC=
|LCCN=
|BNF_ARK=
|ARC=
|Source=_empty_
|Image=1
|Progress=X
|Pages=<pagelist />
|Volumes=
|Remarks=
|Width=
|Css=
|Header=
|Footer=
}}
'''.strip() % title[len('Index:'):]
    base = set_page_wikitext('setup', title, base_content, runner)

    runner.resolve_pages([command.page])
    edit = runner.run_command(CommandPending(0, command))

    assert isinstance(edit, CommandEdit)
    assert edit.base_revision == base
    assert command.page.resolution is None

    revision = get_page_revision(title, runner)
    assert revision['comment'] == '+[[Category:Added cat]]; QuickCategories CI test'
    assert revision['minor']

    expected_page_content = base_content + '\n[[Category:Added cat]]'
    assert revision['slots']['main']['content'] == expected_page_content

    set_page_wikitext('teardown', title, base_content, runner)

def logged_in_session(host: str) -> mwapi.Session:
    if 'MW_USERNAME' not in os.environ or 'MW_PASSWORD' not in os.environ:
        pytest.skip('MediaWiki credentials not provided')
    session = mwapi.Session(host, user_agent='QuickCategories test (mail@lucaswerkmeister.de)')
    lgtoken = session.get(action='query',
                          meta='tokens',
                          type=['login'])['query']['tokens']['logintoken']
    session.post(action='login',
                 lgname=os.environ['MW_USERNAME'],
                 lgpassword=os.environ['MW_PASSWORD'],
                 lgtoken=lgtoken)
    return session

def set_page_wikitext(
        summary: str,
        title: str,
        wikitext: str,
        runner: Runner,
        watchlist_param: WatchlistParam = WatchlistParam.preferences,
) -> int:
    response = runner.session.post(**{'action': 'edit',
                                      'title': title,
                                      'text': wikitext,
                                      'summary': summary,
                                      'watchlist': watchlist_param.name,
                                      'token': runner.csrf_token,
                                      'assert': 'user'})
    if 'nochange' in response['edit']:
        return get_page_revision(title, runner)['revid']
    else:
        return response['edit']['newrevid']

def get_page_revision(title: str, runner: Runner) -> dict:
    response = runner.session.get(action='query',
                                  titles=[title],
                                  prop=['revisions'],
                                  rvprop=['content', 'flags', 'comment', 'ids'],
                                  rvslots=['main'],
                                  formatversion=2)
    return response['query']['pages'][0]['revisions'][0]

def test_with_nochange() -> None:
    curtimestamp = '2019-03-11T23:33:30Z'
    session = FakeSession(
        {
            'curtimestamp': curtimestamp,
            'query': {
                'tokens': {'csrftoken': '+\\'},
                'pages': [
                    {
                        'pageid': 58692,
                        'ns': 0,
                        'title': 'Main page',
                        'revisions': [
                            {
                                'revid': 195259,
                                'parentid': 114947,
                                'timestamp': '2014-02-23T15:14:40Z',
                                'slots': {
                                    'main': {
                                        'contentmodel': 'wikitext',
                                        'contentformat': 'text/x-wiki',
                                        'content': 'Unit Testing 1, 2, 3... External link: http://some-fake-site.com/?p=1774943982 Hit me with a captcha...',
                                    },
                                },
                            },
                        ],
                    },
                ],
                'namespaces': {
                    '14': {
                        'id': 14,
                        'name': 'Category',
                        'canonical': 'Category',
                        'case': 'first-letter',
                    },
                },
                'namespacealiases': [],
                'allmessages': [
                    {
                        'name': 'comma-separator',
                        'content': ', ',
                    },
                    {
                        'name': 'semicolon-separator',
                        'content': '; ',
                    },
                    {
                        'name': 'parentheses',
                        'content': '($1)',
                    },
                ],
            },
        },
        {
            'edit': {
                'result': 'Success',
                'pageid': 58692,
                'title': 'Main page',
                'contentmodel': 'wikitext',
                'nochange': ''
            }
        }
    )
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    command = Command(Page('Main page', True), [AddCategoryAction('Added cat')])
    command_pending = CommandPending(0, command)
    command_record = runner.run_command(command_pending)

    assert isinstance(command_record, CommandNoop)
    assert command_record.revision == 195259
    assert command.page.resolution is None

def test_with_missing_page() -> None:
    curtimestamp = '2019-03-11T23:33:30Z'
    session = FakeSession({
        'curtimestamp': curtimestamp,
        'query': {
            'tokens': {'csrftoken': '+\\'},
            'pages': [
                {
                    'ns': 0,
                    'title': 'Missing page',
                    'missing': True,
                },
            ],
            'namespaces': {
                '14': {
                    'id': 14,
                    'name': 'Category',
                    'canonical': 'Category',
                    'case': 'first-letter',
                },
            },
            'namespacealiases': [],
            'allmessages': [
                {
                    'name': 'comma-separator',
                    'content': ', ',
                },
                {
                    'name': 'semicolon-separator',
                    'content': '; ',
                },
                {
                    'name': 'parentheses',
                    'content': '($1)',
                },
            ],
        },
    })
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    page = Page('Missing page', True)

    runner.resolve_pages([page])

    assert page.resolution == {
        'missing': True,
        'curtimestamp': curtimestamp,
    }

    command = Command(page, [AddCategoryAction('Added cat')])
    command_pending = CommandPending(0, command)
    command_record = runner.run_command(command_pending)

    assert command_record == CommandPageMissing(command_pending.id, command_pending.command, curtimestamp)

def test_with_missing_page_unnormalized() -> None:
    curtimestamp = '2019-03-11T23:33:30Z'
    session = FakeSession({
        'curtimestamp': curtimestamp,
        'query': {
            'tokens': {'csrftoken': '+\\'},
            'pages': [
                {
                    'ns': 0,
                    'title': 'Missing page',
                    'missing': True,
                },
            ],
            'normalized': [
                {
                    'from': 'missing page',
                    'to': 'Missing page',
                },
            ],
            'namespaces': {
                '14': {
                    'id': 14,
                    'name': 'Category',
                    'canonical': 'Category',
                    'case': 'first-letter',
                },
            },
            'namespacealiases': [],
            'allmessages': [
                {
                    'name': 'comma-separator',
                    'content': ', ',
                },
                {
                    'name': 'semicolon-separator',
                    'content': '; ',
                },
                {
                    'name': 'parentheses',
                    'content': '($1)',
                },
            ],
        },
    })
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    page = Page('missing page', True)

    runner.resolve_pages([page])

    assert page.resolution == {
        'missing': True,
        'curtimestamp': curtimestamp,
    }

    command_pending = CommandPending(0, Command(page, [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert command_record == CommandPageMissing(command_pending.id, command_pending.command, curtimestamp)

def test_with_missing_page_redirect_resolve() -> None:
    curtimestamp = '2019-03-11T23:33:30Z'
    session = FakeSession({
        'curtimestamp': curtimestamp,
        'query': {
            'tokens': {'csrftoken': '+\\'},
            'pages': [
                {
                    'ns': 0,
                    'title': 'Redirect to missing page',
                    'invalid': True,  # if Runner doesn’t resolve redirect, it’ll return CommandTitleInvalid instead of CommandPageMissing
                },
                {
                    'ns': 0,
                    'title': 'Missing page',
                    'missing': True,
                },
            ],
            'redirects': [
                {
                    'from': 'Redirect to missing page',
                    'to': 'Missing page',
                },
            ],
            'namespaces': {
                '14': {
                    'id': 14,
                    'name': 'Category',
                    'canonical': 'Category',
                    'case': 'first-letter',
                },
            },
            'namespacealiases': [],
            'allmessages': [
                {
                    'name': 'comma-separator',
                    'content': ', ',
                },
                {
                    'name': 'semicolon-separator',
                    'content': '; ',
                },
                {
                    'name': 'parentheses',
                    'content': '($1)',
                },
            ],
        },
    })
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    page = Page('Redirect to missing page', True)

    runner.resolve_pages([page])

    assert page.resolution == {
        'missing': True,
        'curtimestamp': curtimestamp,
    }

    command_pending = CommandPending(0, Command(page, [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert command_record == CommandPageMissing(command_pending.id, command_pending.command, curtimestamp)

@pytest.mark.parametrize('resolve_redirects', [False, None])
def test_with_missing_page_redirect_without_resolve(resolve_redirects: Optional[bool]) -> None:
    curtimestamp = '2019-03-11T23:33:30Z'
    session = FakeSession({
        'curtimestamp': curtimestamp,
        'query': {
            'tokens': {'csrftoken': '+\\'},
            'pages': [
                {
                    'ns': 0,
                    'title': 'Redirect to missing page',
                    'missing': True,
                },
                # no entry for Missing page, if Runner resolves redirect it should crash
            ],
            'redirects': [
                {
                    'from': 'Redirect to missing page',
                    'to': 'Missing page',
                },
            ],
            'namespaces': {
                '14': {
                    'id': 14,
                    'name': 'Category',
                    'canonical': 'Category',
                    'case': 'first-letter',
                },
            },
            'namespacealiases': [],
            'allmessages': [
                {
                    'name': 'comma-separator',
                    'content': ', ',
                },
                {
                    'name': 'semicolon-separator',
                    'content': '; ',
                },
                {
                    'name': 'parentheses',
                    'content': '($1)',
                },
            ],
        },
    })
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    page = Page('Redirect to missing page', resolve_redirects)

    runner.resolve_pages([page])

    assert page.resolution == {
        'missing': True,
        'curtimestamp': curtimestamp,
    }

    command_pending = CommandPending(0, Command(page, [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert command_record == CommandPageMissing(command_pending.id, command_pending.command, curtimestamp)

def test_with_missing_page_unnormalized_redirect() -> None:
    curtimestamp = '2019-03-11T23:33:30Z'
    session = FakeSession({
        'curtimestamp': curtimestamp,
        'query': {
            'tokens': {'csrftoken': '+\\'},
            'pages': [
                {
                    'ns': 0,
                    'title': 'Missing page',
                    'missing': True,
                },
            ],
            'normalized': [
                {
                    'from': 'redirect to missing page',
                    'to': 'Redirect to missing page',
                },
            ],
            'redirects': [
                {
                    'from': 'Redirect to missing page',
                    'to': 'Missing page',
                },
            ],
            'namespaces': {
                '14': {
                    'id': 14,
                    'name': 'Category',
                    'canonical': 'Category',
                    'case': 'first-letter',
                },
            },
            'namespacealiases': [],
            'allmessages': [
                {
                    'name': 'comma-separator',
                    'content': ', ',
                },
                {
                    'name': 'semicolon-separator',
                    'content': '; ',
                },
                {
                    'name': 'parentheses',
                    'content': '($1)',
                },
            ],
        },
    })
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    page = Page('redirect to missing page', True)

    runner.resolve_pages([page])

    assert page.resolution == {
        'missing': True,
        'curtimestamp': curtimestamp,
    }

    command_pending = CommandPending(0, Command(page, [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert command_record == CommandPageMissing(command_pending.id, command_pending.command, curtimestamp)

def test_with_invalid_title() -> None:
    curtimestamp = '2019-03-11T23:33:30Z'
    session = FakeSession({
        'curtimestamp': curtimestamp,
        'query': {
            'tokens': {'csrftoken': '+\\'},
            'pages': [
                {
                    'title': 'Invalid%20title',
                    'invalidreason': 'The requested page title contains invalid characters: "%20".',
                    'invalid': True,
                },
            ],
            'namespaces': {
                '14': {
                    'id': 14,
                    'name': 'Category',
                    'canonical': 'Category',
                    'case': 'first-letter',
                },
            },
            'namespacealiases': [],
            'allmessages': [
                {
                    'name': 'comma-separator',
                    'content': ', ',
                },
                {
                    'name': 'semicolon-separator',
                    'content': '; ',
                },
                {
                    'name': 'parentheses',
                    'content': '($1)',
                },
            ],
        },
    })
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    page = Page('Invalid%20title', True)

    runner.resolve_pages([page])

    assert page.resolution == {
        'invalid': True,
        'curtimestamp': curtimestamp,
    }

    command_pending = CommandPending(0, Command(page, [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert command_record == CommandTitleInvalid(command_pending.id, command_pending.command, curtimestamp)

def test_with_empty_title() -> None:
    curtimestamp = '2023-02-14T20:51:21Z'

    def get_response(**kwargs: Any) -> dict:
        if 'meta' in kwargs:
            return {
                'query': {
                    'tokens': {'csrftoken': '+\\'},
                    'namespaces': {
                        '14': {
                            'id': 14,
                            'name': 'Category',
                            'canonical': 'Category',
                            'case': 'first-letter',
                        },
                    },
                    'namespacealiases': [],
                    'allmessages': [
                        {
                            'name': 'comma-separator',
                            'content': ', ',
                        },
                        {
                            'name': 'semicolon-separator',
                            'content': '; ',
                        },
                        {
                            'name': 'parentheses',
                            'content': '($1)',
                        },
                    ],
                },
            }
        else:
            return {
                'curtimestamp': curtimestamp,
                # no 'query'
            }

    session = FakeSession(get_response)
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    page = Page('', True)

    runner.resolve_pages([page])

    assert page.resolution == {
        'invalid': True,
        'curtimestamp': curtimestamp,
    }

    command_pending = CommandPending(0, Command(page, [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert command_record == CommandTitleInvalid(command_pending.id, command_pending.command, curtimestamp)

def test_with_hash_title() -> None:
    curtimestamp = '2023-02-14T20:51:21Z'
    session = FakeSession({
        'curtimestamp': curtimestamp,
        'query': {
            'tokens': {'csrftoken': '+\\'},
            'normalized': [
                {
                    'from': '#',
                    'to': '',
                },
            ],
            # notice there’s no actual pages for ''
            'namespaces': {
                '14': {
                    'id': 14,
                    'name': 'Category',
                    'canonical': 'Category',
                    'case': 'first-letter',
                },
            },
            'namespacealiases': [],
            'allmessages': [
                {
                    'name': 'comma-separator',
                    'content': ', ',
                },
                {
                    'name': 'semicolon-separator',
                    'content': '; ',
                },
                {
                    'name': 'parentheses',
                    'content': '($1)',
                },
            ],
        },
    })
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    page = Page('#', True)

    runner.resolve_pages([page])

    assert page.resolution == {
        'invalid': True,
        'curtimestamp': curtimestamp,
    }

    command_pending = CommandPending(0, Command(page, [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert command_record == CommandTitleInvalid(command_pending.id, command_pending.command, curtimestamp)

def test_with_unnormalized_interwiki_title() -> None:
    curtimestamp = '2022-02-15T18:46:30Z'
    session = FakeSession({
        'curtimestamp': curtimestamp,
        'query': {
            'tokens': {'csrftoken': '+\\'},
            'normalized': [
                {
                    'from': 'Commons: Sandbox',
                    'to': 'commons:Sandbox',
                },
            ],
            'interwiki': [
                {
                    'title': 'commons:Sandbox',
                    'iw': 'commons',
                },
            ],
            'namespaces': {
                '14': {
                    'id': 14,
                    'name': 'Category',
                    'canonical': 'Category',
                    'case': 'first-letter',
                },
            },
            'namespacealiases': [],
            'allmessages': [
                {
                    'name': 'comma-separator',
                    'content': ', ',
                },
                {
                    'name': 'semicolon-separator',
                    'content': '; ',
                },
                {
                    'name': 'parentheses',
                    'content': '($1)',
                },
            ],
        },
    })
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    page = Page('Commons: Sandbox', True)

    runner.resolve_pages([page])

    assert page.resolution == {
        'interwiki': True,
        'curtimestamp': curtimestamp,
    }

    command_pending = CommandPending(0, Command(page, [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert command_record == CommandTitleInterwiki(command_pending.id, command_pending.command, curtimestamp)

def test_with_protected_page() -> None:
    curtimestamp = '2019-03-11T23:33:30Z'
    session = FakeSession(
        {
            'curtimestamp': curtimestamp,
            'query': {
                'tokens': {'csrftoken': '+\\'},
                'pages': [
                    {
                        'pageid': 58692,
                        'ns': 0,
                        'title': 'Main page',
                        'revisions': [
                            {
                                'revid': 195259,
                                'parentid': 114947,
                                'timestamp': '2014-02-23T15:14:40Z',
                                'slots': {
                                    'main': {
                                        'contentmodel': 'wikitext',
                                        'contentformat': 'text/x-wiki',
                                        'content': 'Unit Testing 1, 2, 3... External link: http://some-fake-site.com/?p=1774943982 Hit me with a captcha...',
                                    },
                                },
                            },
                        ],
                    },
                ],
                'namespaces': {
                    '14': {
                        'id': 14,
                        'name': 'Category',
                        'canonical': 'Category',
                        'case': 'first-letter',
                    },
                },
                'namespacealiases': [],
                'allmessages': [
                    {
                        'name': 'comma-separator',
                        'content': ', ',
                    },
                    {
                        'name': 'semicolon-separator',
                        'content': '; ',
                    },
                    {
                        'name': 'parentheses',
                        'content': '($1)',
                    },
                ],
            },
        },
        mwapi.errors.APIError('protectedpage', 'This page has been protected to prevent editing or other actions.', None)
    )
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    command_pending = CommandPending(0, Command(Page('Main page', True), [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert command_record == CommandPageProtected(command_pending.id, command_pending.command, curtimestamp)

def test_with_bad_content_format() -> None:
    session = logged_in_session('https://test.wikipedia.org')
    title = 'User:Lucas Werkmeister/test-styles.css'
    command = Command(Page(title, True), [AddCategoryAction('Added cat')])
    runner = Runner(session, WatchlistParam.preferences)

    record = runner.run_command(CommandPending(0, command))

    assert isinstance(record, CommandPageBadContentFormat)
    assert record.content_format == 'text/css'
    assert record.content_model == 'css'

def test_with_edit_conflict() -> None:
    curtimestamp = '2019-03-11T23:33:30Z'
    session = FakeSession(
        {
            'curtimestamp': curtimestamp,
            'query': {
                'tokens': {'csrftoken': '+\\'},
                'pages': [
                    {
                        'pageid': 58692,
                        'ns': 0,
                        'title': 'Main page',
                        'revisions': [
                            {
                                'revid': 195259,
                                'parentid': 114947,
                                'timestamp': '2014-02-23T15:14:40Z',
                                'slots': {
                                    'main': {
                                        'contentmodel': 'wikitext',
                                        'contentformat': 'text/x-wiki',
                                        'content': 'Unit Testing 1, 2, 3... External link: http://some-fake-site.com/?p=1774943982 Hit me with a captcha...',
                                    },
                                },
                            },
                        ],
                    },
                ],
                'namespaces': {
                    '14': {
                        'id': 14,
                        'name': 'Category',
                        'canonical': 'Category',
                        'case': 'first-letter',
                    },
                },
                'namespacealiases': [],
                'allmessages': [
                    {
                        'name': 'comma-separator',
                        'content': ', ',
                    },
                    {
                        'name': 'semicolon-separator',
                        'content': '; ',
                    },
                    {
                        'name': 'parentheses',
                        'content': '($1)',
                    },
                ],
            },
        },
        mwapi.errors.APIError('editconflict', 'Edit conflict: $1', None)
    )
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    page = Page('Main page', True)

    runner.resolve_pages([page])

    assert page.resolution is not None

    command_pending = CommandPending(0, Command(page, [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert command_record == CommandEditConflict(command_pending.id, command_pending.command)
    assert page.resolution is None

def test_with_maxlag_exceeded() -> None:
    curtimestamp = '2019-03-11T23:33:30Z'
    session = FakeSession(
        {
            'curtimestamp': curtimestamp,
            'query': {
                'tokens': {'csrftoken': '+\\'},
                'pages': [
                    {
                        'pageid': 58692,
                        'ns': 0,
                        'title': 'Main page',
                        'revisions': [
                            {
                                'revid': 195259,
                                'parentid': 114947,
                                'timestamp': '2014-02-23T15:14:40Z',
                                'slots': {
                                    'main': {
                                        'contentmodel': 'wikitext',
                                        'contentformat': 'text/x-wiki',
                                        'content': 'Unit Testing 1, 2, 3... External link: http://some-fake-site.com/?p=1774943982 Hit me with a captcha...',
                                    },
                                },
                            },
                        ],
                    },
                ],
                'namespaces': {
                    '14': {
                        'id': 14,
                        'name': 'Category',
                        'canonical': 'Category',
                        'case': 'first-letter',
                    },
                },
                'namespacealiases': [],
                'allmessages': [
                    {
                        'name': 'comma-separator',
                        'content': ', ',
                    },
                    {
                        'name': 'semicolon-separator',
                        'content': '; ',
                    },
                    {
                        'name': 'parentheses',
                        'content': '($1)',
                    },
                ],
            },
        },
        mwapi.errors.APIError('maxlag', 'Waiting for 10.64.48.35: 0.36570191383362 seconds lagged.', None)
    )
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    page = Page('Main page', True)

    runner.resolve_pages([page])

    assert page.resolution is not None

    command_pending = CommandPending(0, Command(page, [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert isinstance(command_record, CommandMaxlagExceeded)
    assert command_record.retry_after.tzinfo == datetime.timezone.utc
    assert page.resolution is not None

def test_with_blocked() -> None:
    curtimestamp = '2019-03-11T23:33:30Z'
    session = FakeSession(
        {
            'curtimestamp': curtimestamp,
            'query': {
                'tokens': {'csrftoken': '+\\'},
                'pages': [
                    {
                        'pageid': 58692,
                        'ns': 0,
                        'title': 'Main page',
                        'revisions': [
                            {
                                'revid': 195259,
                                'parentid': 114947,
                                'timestamp': '2014-02-23T15:14:40Z',
                                'slots': {
                                    'main': {
                                        'contentmodel': 'wikitext',
                                        'contentformat': 'text/x-wiki',
                                        'content': 'Unit Testing 1, 2, 3... External link: http://some-fake-site.com/?p=1774943982 Hit me with a captcha...',
                                    },
                                },
                            },
                        ],
                    },
                ],
                'namespaces': {
                    '14': {
                        'id': 14,
                        'name': 'Category',
                        'canonical': 'Category',
                        'case': 'first-letter',
                    },
                },
                'namespacealiases': [],
                'allmessages': [
                    {
                        'name': 'comma-separator',
                        'content': ', ',
                    },
                    {
                        'name': 'semicolon-separator',
                        'content': '; ',
                    },
                    {
                        'name': 'parentheses',
                        'content': '($1)',
                    },
                ],
            },
        },
        mwapi.errors.APIError('blocked', 'You have been blocked from editing.', None)
    )
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    page = Page('Main page', True)

    runner.resolve_pages([page])

    assert page.resolution is not None

    command_pending = CommandPending(0, Command(page, [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert isinstance(command_record, CommandBlocked)
    assert not command_record.auto
    # would be nice to assert command_record.blockinfo once Runner can record it

def test_with_autoblocked() -> None:
    curtimestamp = '2019-03-11T23:33:30Z'
    session = FakeSession(
        {
            'curtimestamp': curtimestamp,
            'query': {
                'tokens': {'csrftoken': '+\\'},
                'pages': [
                    {
                        'pageid': 58692,
                        'ns': 0,
                        'title': 'Main page',
                        'revisions': [
                            {
                                'revid': 195259,
                                'parentid': 114947,
                                'timestamp': '2014-02-23T15:14:40Z',
                                'slots': {
                                    'main': {
                                        'contentmodel': 'wikitext',
                                        'contentformat': 'text/x-wiki',
                                        'content': 'Unit Testing 1, 2, 3... External link: http://some-fake-site.com/?p=1774943982 Hit me with a captcha...',
                                    },
                                },
                            },
                        ],
                    },
                ],
                'namespaces': {
                    '14': {
                        'id': 14,
                        'name': 'Category',
                        'canonical': 'Category',
                        'case': 'first-letter',
                    },
                },
                'namespacealiases': [],
                'allmessages': [
                    {
                        'name': 'comma-separator',
                        'content': ', ',
                    },
                    {
                        'name': 'semicolon-separator',
                        'content': '; ',
                    },
                    {
                        'name': 'parentheses',
                        'content': '($1)',
                    },
                ],
            },
        },
        mwapi.errors.APIError('autoblocked', 'Your IP address has been blocked automatically, because it was used by a blocked user.', None)
    )
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    page = Page('Main page', True)

    runner.resolve_pages([page])

    assert page.resolution is not None

    command_pending = CommandPending(0, Command(page, [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert isinstance(command_record, CommandBlocked)
    assert command_record.auto
    # would be nice to assert command_record.blockinfo once Runner can record it

def test_with_readonly() -> None:
    curtimestamp = '2019-03-11T23:33:30Z'
    session = FakeSession(
        {
            'curtimestamp': curtimestamp,
            'query': {
                'tokens': {'csrftoken': '+\\'},
                'pages': [
                    {
                        'pageid': 58692,
                        'ns': 0,
                        'title': 'Main page',
                        'revisions': [
                            {
                                'revid': 195259,
                                'parentid': 114947,
                                'timestamp': '2014-02-23T15:14:40Z',
                                'slots': {
                                    'main': {
                                        'contentmodel': 'wikitext',
                                        'contentformat': 'text/x-wiki',
                                        'content': 'Unit Testing 1, 2, 3... External link: http://some-fake-site.com/?p=1774943982 Hit me with a captcha...',
                                    },
                                },
                            },
                        ],
                    },
                ],
                'namespaces': {
                    '14': {
                        'id': 14,
                        'name': 'Category',
                        'canonical': 'Category',
                        'case': 'first-letter',
                    },
                },
                'namespacealiases': [],
                'allmessages': [
                    {
                        'name': 'comma-separator',
                        'content': ', ',
                    },
                    {
                        'name': 'semicolon-separator',
                        'content': '; ',
                    },
                    {
                        'name': 'parentheses',
                        'content': '($1)',
                    },
                ],
            },
        },
        mwapi.errors.APIError('readonly', 'The wiki is currently in read-only mode.', None)
    )
    session.host = 'test.wikidata.org'
    runner = Runner(session, WatchlistParam.preferences)

    page = Page('Main page', True)

    runner.resolve_pages([page])

    assert page.resolution is not None

    command_pending = CommandPending(0, Command(page, [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert isinstance(command_record, CommandWikiReadOnly)
    # would be nice to assert command_record.reason once Runner can record it
