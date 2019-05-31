import cachetools
import mwapi # type: ignore
import threading
from typing import Any
import warnings


_sitematrix_cache = cachetools.TTLCache(maxsize=1, ttl=24*60*60) # type: cachetools.TTLCache[Any, dict]
_sitematrix_cache_lock = threading.RLock()


@cachetools.cached(cache=_sitematrix_cache,
                   key=lambda session: '#sitematrix',
                   lock=_sitematrix_cache_lock)
def _get_sitematrix(session: mwapi.Session) -> dict:
    sitematrix = {}
    result = session.get(action='sitematrix',
                         formatversion=2)
    for k, v in result['sitematrix'].items():
        if k == 'count':
            if v > 5000:
                warnings.warn('sitematrix reports more than 5000 sites (%d), continuation might be necessary' % v)
            continue
        if k == 'specials':
            sites = v
        else:
            sites = v['site']
        for site in sites:
            sitematrix[site['dbname']] = site
    return sitematrix


def dbname_to_domain(session: mwapi.Session, dbname: str) -> str:
    sitematrix = _get_sitematrix(session)
    url = sitematrix[dbname]['url']
    assert url.startswith('https://')
    return url[len('https://'):]
