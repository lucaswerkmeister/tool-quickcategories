import mwapi # type: ignore
import pytest # type: ignore

from sitematrix import dbname_to_domain, _sitematrix_cache, _sitematrix_cache_lock

from test_utils import FakeSession, internet_test


@pytest.fixture(autouse=True)
def clean_sitematrix():
    with _sitematrix_cache_lock:
        _sitematrix_cache.clear()
    yield
    with _sitematrix_cache_lock:
        _sitematrix_cache.clear()


def test_dbname_to_domain_fake_session():
    session = FakeSession({
        'sitematrix': {
            'count': 4,
            '0': {
                'code': 'en',
                'name': 'English',
                'site': [
                    {
                        'url': 'https://en.wikipedia.org',
                        'dbname': 'enwiki',
                        'code': 'wiki',
                        'sitename': 'Wikipedia',
                    },
                    {
                        'url': 'https://en.wiktionary.org',
                        'dbname': 'enwiktionary',
                        'code': 'wiktionary',
                        'sitename': 'Wiktionary',
                    },
                ],
                'dir': 'ltr',
                'localname': 'English',
            },
            '1': {
                'code': 'pt',
                'name': 'português',
                'site': [
                    {
                        'url': 'https://pt.wikipedia.org',
                        'dbname': 'ptwiki',
                        'code': 'wiki',
                        'sitename': 'Wikipedia',
                    },
                ],
                'dir': 'ltr',
                'localname': 'Portuguese',
            },
            'specials': [
                {
                    'url': 'https://www.wikidata.org',
                    'dbname': 'wikidatawiki',
                    'code': 'wikidata',
                    'lang': 'wikidata',
                    'sitename': 'Wikipedia',
                },
            ],
        },
    })

    assert dbname_to_domain(session, 'enwiki') == 'en.wikipedia.org'
    assert dbname_to_domain(session, 'enwiktionary') == 'en.wiktionary.org'
    assert dbname_to_domain(session, 'ptwiki') == 'pt.wikipedia.org'
    assert dbname_to_domain(session, 'wikidatawiki') == 'www.wikidata.org'


def test_dbname_to_domain_warns_for_fake_session_with_too_many_sites():
    session = FakeSession({
        'sitematrix': {
            'count': 9001,
            '0': {
                'code': 'en',
                'name': 'English',
                'site': [
                    {
                        'url': 'https://en.wikipedia.org',
                        'dbname': 'enwiki',
                        'code': 'wiki',
                        'sitename': 'Wikipedia',
                    },
                ],
                'dir': 'ltr',
                'localname': 'English',
            },
        },
    })

    with pytest.warns(UserWarning):
        dbname_to_domain(session, 'enwiki') == 'en.wikipedia.org'


@internet_test
def test_dbname_to_domain_real_session():
    session = mwapi.Session('https://meta.wikimedia.org', user_agent='QuickCategories test (mail@lucaswerkmeister.de)')

    assert dbname_to_domain(session, 'enwiki') == 'en.wikipedia.org'
    assert dbname_to_domain(session, 'enwiktionary') == 'en.wiktionary.org'
    assert dbname_to_domain(session, 'ptwiki') == 'pt.wikipedia.org'
    assert dbname_to_domain(session, 'wikidatawiki') == 'www.wikidata.org'
