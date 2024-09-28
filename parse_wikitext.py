import bs4
import cachetools
from markupsafe import Markup
import mwapi  # type: ignore
import threading
from typing import cast


summary_cache: cachetools.LRUCache[tuple[str, str], Markup] = cachetools.LRUCache(maxsize=1024)
summary_cache_lock = threading.RLock()


@cachetools.cached(cache=summary_cache,
                   key=lambda session, summary: (session.host, summary),
                   lock=summary_cache_lock)
def parse_summary(session: mwapi.Session, summary: str) -> Markup:
    """Parses a summary text or fragment into HTML."""

    try:
        response = session.get(action='parse',
                               summary=summary,
                               prop=[],
                               title='Special:X',  # T279585
                               formatversion=2)
    except mwapi.errors.APIError as e:
        print("Error formatting summary {!r}: {}".format(summary, e))
        return Markup.escape(summary)
    else:
        summary_html = response['parse']['parsedsummary']
        return fix_markup(summary_html, session.host)

def fix_markup(html: str, host: str) -> Markup:
    soup = bs4.BeautifulSoup(html, 'html.parser')
    for link in soup.select('a[href]'):
        href = cast(str, link['href'])  # href is never multi-valued
        if href.startswith('/') and not href.startswith('//'):
            link['href'] = host + href
    return Markup(str(soup))
