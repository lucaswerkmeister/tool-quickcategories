import mwapi
import os
import pytest

import batch
import runner

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

    command = batch.Command('QuickCategories CI Test', [batch.AddCategoryAction('Added cat'),
                                                        batch.AddCategoryAction('Already present cat'),
                                                        batch.RemoveCategoryAction('Removed cat'),
                                                        batch.RemoveCategoryAction('Not present cat')])
    csrftoken = session.get(action='query',
                            meta='tokens')['query']['tokens']['csrftoken']
    session.post(action='edit',
                 title=command.page,
                 text='Test page for the QuickCategories tool.\n[[Category:Already present cat]]\n[[Category:Removed cat]]\nBottom text',
                 summary='setup',
                 token=csrftoken)
    runner.Runner().run_command(command, session)

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
