import mwapi
import os
import pytest

from action import AddCategoryAction, RemoveCategoryAction
from command import Command
from runner import Runner

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
    session.post(action='edit',
                 title=command.page,
                 text='Test page for the QuickCategories tool.\n[[Category:Already present cat]]\n[[Category:Removed cat]]\nBottom text',
                 summary='setup',
                 token=csrftoken)
    Runner().run_command(command, session)

    actual = session.get(action='query',
                         titles=[command.page],
                         prop=['revisions'],
                         rvprop=['content'],
                         rvslots=['main'],
                         rvlimit=1,
                         formatversion=2)['query']['pages'][0]['revisions'][0]['slots']['main']['content']
    session.post(action='edit',
                 title=command.page,
                 text='Test page for the QuickCategories tool.',
                 summary='teardown',
                 token=csrftoken)
    expected = 'Test page for the QuickCategories tool.\n[[Category:Already present cat]]\n[[Category:Added cat]]\nBottom text'
    assert expected == actual
