import mwapi # type: ignore
import pytest # type: ignore

from sitematrix import dbname_to_domain, domain_to_dbname, _sitematrix_cache, _sitematrix_cache_lock

from test_utils import FakeSession


@pytest.fixture(autouse=True)
def clean_sitematrix():
    with _sitematrix_cache_lock:
        _sitematrix_cache.clear()
    yield
    with _sitematrix_cache_lock:
        _sitematrix_cache.clear()


fake_session = FakeSession({
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
fake_session_with_too_many_sites = FakeSession({
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


def test_dbname_to_domain_fake_session():
    assert dbname_to_domain(fake_session, 'enwiki') == 'en.wikipedia.org'
    assert dbname_to_domain(fake_session, 'enwiktionary') == 'en.wiktionary.org'
    assert dbname_to_domain(fake_session, 'ptwiki') == 'pt.wikipedia.org'
    assert dbname_to_domain(fake_session, 'wikidatawiki') == 'www.wikidata.org'


def test_dbname_to_domain_warns_for_fake_session_with_too_many_sites():
    with pytest.warns(UserWarning):
        dbname_to_domain(fake_session_with_too_many_sites, 'enwiki') == 'en.wikipedia.org'


def test_dbname_to_domain_real_session(internet_connection):
    session = mwapi.Session('https://meta.wikimedia.org', user_agent='QuickCategories test (mail@lucaswerkmeister.de)')

    assert dbname_to_domain(session, 'enwiki') == 'en.wikipedia.org'
    assert dbname_to_domain(session, 'enwiktionary') == 'en.wiktionary.org'
    assert dbname_to_domain(session, 'ptwiki') == 'pt.wikipedia.org'
    assert dbname_to_domain(session, 'wikidatawiki') == 'www.wikidata.org'


def test_domain_to_dbname_fake_session():
    assert domain_to_dbname(fake_session, 'en.wikipedia.org') == 'enwiki'
    assert domain_to_dbname(fake_session, 'en.wiktionary.org') == 'enwiktionary'
    assert domain_to_dbname(fake_session, 'pt.wikipedia.org') == 'ptwiki'
    assert domain_to_dbname(fake_session, 'www.wikidata.org') == 'wikidatawiki'


def test_domain_to_dbname_warns_for_fake_session_with_too_many_sites():
    with pytest.warns(UserWarning):
        domain_to_dbname(fake_session_with_too_many_sites, 'en.wikipedia.org') == 'enwiki'


def test_domain_to_dbname_real_session(internet_connection):
    session = mwapi.Session('https://meta.wikimedia.org', user_agent='QuickCategories test (mail@lucaswerkmeister.de)')

    assert domain_to_dbname(session, 'en.wikipedia.org') == 'enwiki'
    assert domain_to_dbname(session, 'en.wiktionary.org') == 'enwiktionary'
    assert domain_to_dbname(session, 'pt.wikipedia.org') == 'ptwiki'
    assert domain_to_dbname(session, 'www.wikidata.org') == 'wikidatawiki'
