import datetime
import mwapi # type: ignore
import os
import pytest # type: ignore

from action import AddCategoryAction, RemoveCategoryAction
from command import Command, CommandPending, CommandEdit, CommandNoop, CommandPageMissing, CommandPageProtected, CommandEditConflict, CommandMaxlagExceeded, CommandBlocked, CommandWikiReadOnly
from runner import Runner

from test_utils import FakeSession

def test_run_command():
    if 'MW_USERNAME' not in os.environ or 'MW_PASSWORD' not in os.environ:
        pytest.skip('MediaWiki credentials not provided')
    session = mwapi.Session('https://test.wikipedia.org', user_agent='QuickCategories test (mail@lucaswerkmeister.de)')
    lgtoken = session.get(action='query',
                          meta='tokens',
                          type=['login'])['query']['tokens']['logintoken']
    session.post(action='login',
                 lgname=os.environ['MW_USERNAME'],
                 lgpassword=os.environ['MW_PASSWORD'],
                 lgtoken=lgtoken)

    title = 'QuickCategories CI Test'
    if 'TRAVIS_JOB_NUMBER' in os.environ:
        job_number = os.environ['TRAVIS_JOB_NUMBER']
        title += '/' + job_number[job_number.index('.')+1:]

    command = Command(title, [AddCategoryAction('Added cat'),
                              AddCategoryAction('Already present cat'),
                              RemoveCategoryAction('Removed cat'),
                              RemoveCategoryAction('Not present cat')])
    runner = Runner(session)
    csrftoken = session.get(action='query',
                            meta='tokens')['query']['tokens']['csrftoken']
    setup_edit = session.post(**{'action': 'edit',
                                 'title': command.page,
                                 'text': 'Test page for the QuickCategories tool.\n[[Category:Already present cat]]\n[[Category:Removed cat]]\nBottom text',
                                 'summary': 'setup',
                                 'token': csrftoken,
                                 'assert': 'user'})
    edit = runner.run_command(CommandPending(0, command))

    assert isinstance(edit, CommandEdit)
    assert edit.base_revision == setup_edit['edit']['newrevid']
    assert command.page not in runner.prepared_pages

    actual = session.get(action='query',
                         revids=[edit.revision],
                         prop=['revisions'],
                         rvprop=['content'],
                         rvslots=['main'],
                         formatversion=2)['query']['pages'][0]['revisions'][0]['slots']['main']['content']
    session.post(**{'action': 'edit',
                    'title': command.page,
                    'text': 'Test page for the QuickCategories tool.',
                    'summary': 'teardown',
                    'token': csrftoken,
                    'assert': 'user'})
    expected = 'Test page for the QuickCategories tool.\n[[Category:Already present cat]]\n[[Category:Added cat]]\nBottom text'
    assert expected == actual

def test_with_nochange():
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
    runner = Runner(session)

    command_pending = CommandPending(0, Command('Main page', [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert isinstance(command_record, CommandNoop)
    assert command_record.revision == 195259

def test_with_missing_page():
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
    runner = Runner(session)

    runner.prepare_pages(['Missing page'])

    assert runner.prepared_pages['Missing page'] == {
        'missing': True,
        'curtimestamp': curtimestamp,
    }

    command_pending = CommandPending(0, Command('Missing page', [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert command_record == CommandPageMissing(command_pending.id, command_pending.command, curtimestamp)

def test_with_missing_page_unnormalized():
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
    runner = Runner(session)

    runner.prepare_pages(['missing page'])

    assert runner.prepared_pages['missing page'] == {
        'missing': True,
        'curtimestamp': curtimestamp,
    }

    command_pending = CommandPending(0, Command('missing page', [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert command_record == CommandPageMissing(command_pending.id, command_pending.command, curtimestamp)

def test_with_protected_page():
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
    runner = Runner(session)

    command_pending = CommandPending(0, Command('Main page', [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert command_record == CommandPageProtected(command_pending.id, command_pending.command, curtimestamp)

def test_with_edit_conflict():
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
    runner = Runner(session)

    runner.prepare_pages(['Main page'])

    assert 'Main page' in runner.prepared_pages

    command_pending = CommandPending(0, Command('Main page', [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert command_record == CommandEditConflict(command_pending.id, command_pending.command)
    assert 'Main page' not in runner.prepared_pages

def test_with_maxlag_exceeded():
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
    runner = Runner(session)

    runner.prepare_pages(['Main page'])

    assert 'Main page' in runner.prepared_pages

    command_pending = CommandPending(0, Command('Main page', [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert isinstance(command_record, CommandMaxlagExceeded)
    assert command_record.retry_after.tzinfo == datetime.timezone.utc
    assert 'Main page' in runner.prepared_pages

def test_with_blocked():
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
    runner = Runner(session)

    runner.prepare_pages(['Main page'])

    assert 'Main page' in runner.prepared_pages

    command_pending = CommandPending(0, Command('Main page', [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert isinstance(command_record, CommandBlocked)
    assert not command_record.auto
    # would be nice to assert command_record.blockinfo once Runner can record it

def test_with_autoblocked():
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
    runner = Runner(session)

    runner.prepare_pages(['Main page'])

    assert 'Main page' in runner.prepared_pages

    command_pending = CommandPending(0, Command('Main page', [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert isinstance(command_record, CommandBlocked)
    assert command_record.auto
    # would be nice to assert command_record.blockinfo once Runner can record it

def test_with_readonly():
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
    runner = Runner(session)

    runner.prepare_pages(['Main page'])

    assert 'Main page' in runner.prepared_pages

    command_pending = CommandPending(0, Command('Main page', [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_pending)

    assert isinstance(command_record, CommandWikiReadOnly)
    # would be nice to assert command_record.reason once Runner can record it
