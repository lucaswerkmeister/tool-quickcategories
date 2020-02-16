import bs4  # type: ignore
import cachetools
import flask
import mwapi  # type: ignore
import threading
from typing import Tuple


summary_cache = cachetools.LRUCache(maxsize=1024)  # type: cachetools.LRUCache[Tuple[str, str], flask.Markup]
summary_cache_lock = threading.RLock()


@cachetools.cached(cache=summary_cache,
                   key=lambda session, summary: (session.host, summary),
                   lock=summary_cache_lock)
def parse_summary(session: mwapi.Session, summary: str) -> flask.Markup:
    """Parses a summary text or fragment into HTML."""

    response = session.get(action='parse',
                           summary=summary,
                           prop=[],
                           formatversion=2)
    summary_html = response['parse']['parsedsummary']
    return fix_markup(summary_html, session.host)

def fix_markup(html: str, host: str) -> flask.Markup:
    soup = bs4.BeautifulSoup(html, 'html.parser')
    for link in soup.select('a[href]'):
        href = link['href']
        if href.startswith('/') and not href.startswith('//'):
            link['href'] = host + href
    return flask.Markup(str(soup))
