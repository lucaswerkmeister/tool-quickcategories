import mwapi
import os
import pytest

from action import AddCategoryAction, RemoveCategoryAction
from command import Command, CommandPlan, CommandEdit, CommandPageMissing
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
