import pytest

import app as quickcategories


@pytest.mark.parametrize('domain, expected', [
    # Wikimedia domains we want to use
    ('be-tarask.wikipedia.org', True),
    ('meta.wikimedia.org', True),
    ('ru.wikibooks.org', True),
    ('www.wikidata.org', True),
    ('fr.wikinews.org', True),
    ('la.wikiquote.org', True),
    ('www.wikisource.org', True),
    ('en.wikiversity.org', True),
    ('de.wikivoyage.org', True),
    ('www.mediawiki.org', True),
    ('simple.wiktionary.org', True),
    ('www.wikifunctions.org', True),
    # Wikimedia domains we don’t want to use
    ('www.m.wikidata.org', False),
    ('wikipedia.de', False),
    ('wikimediafoundation.org', False),
    ('w.wiki', False),
    ('wmfusercontent.org', False),
    # other domains
    ('lucaswerkmeister.de', False),
    ('www.lucaswerkmeister.de', False),
    ('starwars.wikia.com', False),
    ('example.com', False),
    ('en.wikipedia.org.google', False),
    # fallback used in new_batch_from_commands() if form parameter is missing
    ('(not provided)', False),
])
def test_is_wikimedia_domain(domain: str, expected: bool) -> None:
    assert expected == quickcategories.is_wikimedia_domain(domain)


def test_slice_from_args_default() -> None:
    assert quickcategories.slice_from_args({}) == (0, 50)

def test_slice_from_args_with_offset() -> None:
    assert quickcategories.slice_from_args({'offset': '50'}) == (50, 50)

def test_slice_from_args_with_limit() -> None:
    assert quickcategories.slice_from_args({'limit': '10'}) == (0, 10)

def test_slice_from_args_with_offset_and_limit() -> None:
    assert quickcategories.slice_from_args({'offset': '25', 'limit': '10'}) == (25, 10)

@pytest.mark.parametrize('offset', [
    '-1',
    'one hundred',
    '; DROP DATABASE; --',
])
def test_slice_from_args_with_invalid_offset(offset: str) -> None:
    assert quickcategories.slice_from_args({'offset': offset}) == (0, 50)

@pytest.mark.parametrize('limit, effective_limit', [
    ('-1', 1),
    ('1000', 500),
    ('two million', 50),
    ('; DROP DATABASE; --', 50),
])
def test_slice_from_args_with_invalid_limit(limit: str, effective_limit: int) -> None:
    assert quickcategories.slice_from_args({'limit': limit}) == (0, effective_limit)


def test_steward_global_user_ids_Martin_Urbanec(internet_connection: None) -> None:
    assert 34722510 in quickcategories.steward_global_user_ids()

def test_steward_global_user_ids_Lucas_Werkmeister(internet_connection: None) -> None:
    assert 46054761 not in quickcategories.steward_global_user_ids()
