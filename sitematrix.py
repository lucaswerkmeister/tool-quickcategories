import cachetools
import mwapi # type: ignore
import threading
from typing import Any, Dict
import warnings


_sitematrix_cache = cachetools.TTLCache(maxsize=1, ttl=24*60*60) # type: cachetools.TTLCache[Any, dict]
_sitematrix_cache_lock = threading.RLock()


@cachetools.cached(cache=_sitematrix_cache,
                   key=lambda session: '#sitematrix',
                   lock=_sitematrix_cache_lock)
def _get_sitematrix(session: mwapi.Session) -> dict:
    sitematrix = {
        'by_dbname': {},
        'by_url': {},
    } # type: Dict[str, Dict[str, dict]]
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
            sitematrix['by_dbname'][site['dbname']] = site
            sitematrix['by_url'][site['url']] = site
    return sitematrix


def dbname_to_domain(session: mwapi.Session, dbname: str) -> str:
    sitematrix = _get_sitematrix(session)
    url = sitematrix['by_dbname'][dbname]['url']
    assert url.startswith('https://')
    return url[len('https://'):]


def domain_to_dbname(session: mwapi.Session, domain: str) -> str:
    sitematrix = _get_sitematrix(session)
    return sitematrix['by_url']['https://' + domain]['dbname']
