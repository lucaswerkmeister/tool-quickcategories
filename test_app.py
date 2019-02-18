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
