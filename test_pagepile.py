import mwapi # type: ignore
import os
import pytest # type: ignore

from pagepile import load_pagepile, create_pagepile


session = mwapi.Session('https://meta.wikimedia.org', user_agent='QuickCategories test (mail@lucaswerkmeister.de)')


def test_load_pagepile_not_empty(internet_connection):
    pile = load_pagepile(session, 24289)
    assert pile == ('ga.wikipedia.org', ['Rose Hill, Derby'])

def test_load_pagepile_empty(internet_connection):
    pile = load_pagepile(session, 12345)
    assert pile == ('www.wikidata.org', [])

def test_load_pagepile_unicode(internet_connection):
    pile = load_pagepile(session, 24172)
    # note: the order of the following list is not the same as on the HTML view –
    # HTML orders by internal ID, JSON by namespace and title
    # (at least as of 2019-05-31, PagePile commit 4880cd7622)
    assert pile == ('he.wikipedia.org', ['א',
                                         'אזור מפרץ סן פרנסיסקו',
                                         'ד',
                                         'דרום פלורידה',
                                         'ה',
                                         'האזור המטרופוליטני פלורנס-מאסל שולס',
                                         'המגלופוליס של צפון מזרח ארצות הברית',
                                         'המטרופולין של טולידו',
                                         'המטרופולין של ניו יורק',
                                         'המטרופולין של קנזס סיטי',
                                         'המטרופולין של שיקגו'])

def test_load_pagepile_error(internet_connection):
    assert load_pagepile(session, 1234) is None


def test_create_pagepile_and_load_pagepile(internet_connection):
    if 'TEST_CREATE_PAGEPILE' not in os.environ:
        pytest.skip('Not creating a new PagePile for this test')

    pages = ['User:Lucas Werkmeister/QuickCategories test page 1',
             'User:Lucas Werkmeister/QuickCategories test page 2',
             'User:Lucas Werkmeister/QuickCategories test page 3']
    pile_id = create_pagepile(session, 'test.wikipedia.org', pages)

    pile = load_pagepile(session, pile_id)
    assert pile == ('test.wikipedia.org', pages)
