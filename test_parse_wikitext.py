from markupsafe import Markup
import mwapi  # type: ignore

import parse_wikitext

from test_utils import FakeSession


def test_parse_summary_two_wikis() -> None:
    title = '[[Kategorie:Wikimedia]]'
    summary1 = '<a class="new" href="https://en.wikipedia.org/w/index.php?title=Kategorie:Wikimedia&amp;action=edit&amp;redlink=1" title="Kategorie:Wikimedia (page does not exist)">Kategorie:Wikimedia</a>'
    session1 = FakeSession({
        'parse': {
            'parsedsummary': summary1,
        },
    })
    session1.host = 'https://en.wikipedia.org'
    assert parse_wikitext.parse_summary(session1, title) == Markup(summary1)
    summary2 = '<a href="https://de.wikipedia.org/wiki/Kategorie:Wikimedia" title="Kategorie:Wikimedia">Kategorie:Wikimedia</a>'
    session2 = FakeSession({
        'parse': {
            'parsedsummary': summary2,
        },
    })
    session2.host = 'https://de.wikipedia.org'
    assert parse_wikitext.parse_summary(session2, title) == Markup(summary2)


def test_parse_summary_error() -> None:
    summary = '<script>alert("xss")</script>'
    session = FakeSession(mwapi.errors.APIError('fake', 'XSS detected!', 'for more information see the mailing list blah blah'))
    session.host = 'https://en.wikipedia.org'
    assert parse_wikitext.parse_summary(session, summary) == Markup('&lt;script&gt;alert(&#34;xss&#34;)&lt;/script&gt;')
