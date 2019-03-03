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
    # fallback used in new_batch() if form parameter is missing
    ('(not provided)', False),
])
def test_is_wikimedia_domain(domain, expected):
    assert expected == quickcategories.is_wikimedia_domain(domain)


def test_slice_from_args_default():
    assert quickcategories.slice_from_args({}) == slice(0, 50)

def test_slice_from_args_with_offset():
    assert quickcategories.slice_from_args({'offset': '50'}) == slice(50, 100)

def test_slice_from_args_with_limit():
    assert quickcategories.slice_from_args({'limit': '10'}) == slice(0, 10)

def test_slice_from_args_with_offset_and_limit():
    assert quickcategories.slice_from_args({'offset': '25', 'limit': '10'}) == slice(25, 35)

@pytest.mark.parametrize('offset', [
    '-1',
    'one hundred',
    '; DROP DATABASE; --',
])
def test_slice_from_args_with_invalid_offset(offset):
    assert quickcategories.slice_from_args({'offset': offset}) == slice(0, 50)

@pytest.mark.parametrize('limit, effective_limit', [
    ('-1', 1),
    ('1000', 500),
    ('two million', 50),
    ('; DROP DATABASE; --', 50),
])
def test_slice_from_args_with_invalid_limit(limit, effective_limit):
    assert quickcategories.slice_from_args({'limit': limit}) == slice(0, effective_limit)
