import datetime
import mwapi
import os
import pytest

from action import AddCategoryAction, RemoveCategoryAction
from command import Command, CommandPlan, CommandEdit, CommandPageMissing, CommandEditConflict, CommandMaxlagExceeded
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

    command = Command('QuickCategories CI Test', [AddCategoryAction('Added cat'),
                                                  AddCategoryAction('Already present cat'),
                                                  RemoveCategoryAction('Removed cat'),
                                                  RemoveCategoryAction('Not present cat')])
    csrftoken = session.get(action='query',
                            meta='tokens')['query']['tokens']['csrftoken']
    setup_edit = session.post(**{'action': 'edit',
                                 'title': command.page,
                                 'text': 'Test page for the QuickCategories tool.\n[[Category:Already present cat]]\n[[Category:Removed cat]]\nBottom text',
                                 'summary': 'setup',
                                 'token': csrftoken,
                                 'assert': 'user'})
    edit = Runner(session).run_command(CommandPlan(0, command))

    assert isinstance(edit, CommandEdit)
    assert edit.base_revision == setup_edit['edit']['newrevid']

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
                    "name": "comma-separator",
                    "content":", ",
                },
                {
                    "name": "semicolon-separator",
                    "content": "; ",
                },
                {
                    "name": "parentheses",
                    "content": "($1)",
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

    command_plan = CommandPlan(0, Command('Missing page', [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_plan)

    assert command_record == CommandPageMissing(command_plan.id, command_plan.command, curtimestamp)

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
                    "name": "comma-separator",
                    "content":", ",
                },
                {
                    "name": "semicolon-separator",
                    "content": "; ",
                },
                {
                    "name": "parentheses",
                    "content": "($1)",
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

    command_plan = CommandPlan(0, Command('missing page', [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_plan)

    assert command_record == CommandPageMissing(command_plan.id, command_plan.command, curtimestamp)

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
                        "name": "comma-separator",
                        "content":", ",
                    },
                    {
                        "name": "semicolon-separator",
                        "content": "; ",
                    },
                    {
                        "name": "parentheses",
                        "content": "($1)",
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

    command_plan = CommandPlan(0, Command('Main page', [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_plan)

    assert command_record == CommandEditConflict(command_plan.id, command_plan.command)
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
                        "name": "comma-separator",
                        "content":", ",
                    },
                    {
                        "name": "semicolon-separator",
                        "content": "; ",
                    },
                    {
                        "name": "parentheses",
                        "content": "($1)",
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

    command_plan = CommandPlan(0, Command('Main page', [AddCategoryAction('Added cat')]))
    command_record = runner.run_command(command_plan)

    assert isinstance(command_record, CommandMaxlagExceeded)
    assert command_record.retry_after.tzinfo == datetime.timezone.utc
    assert 'Main page' in runner.prepared_pages
