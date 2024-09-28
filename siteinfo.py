import cachetools
import mwapi  # type: ignore
import threading
from typing import TypeAlias


CategoryInfo: TypeAlias = tuple[str, list[str], str]
"""The primary name of the category namespace,
all the names with which a category link may be formed,
and the case of the category namespace ("first-letter" or "case-sensitive")."""


_SiteInfo: TypeAlias = tuple[CategoryInfo, dict[str, str]]
"""The category info,
and a dict from message key to message content."""


def _get_siteinfo(session: mwapi.Session) -> _SiteInfo:
    response = session.get(action='query',
                           meta=['siteinfo', 'allmessages'],
                           siprop=['namespaces', 'namespacealiases'],
                           ammessages=['comma-separator', 'semicolon-separator', 'word-separator', 'parentheses'],
                           formatversion=2)

    for namespace in response['query']['namespaces'].values():
        if namespace.get('canonical') == 'Category':
            category_namespace_id = namespace['id']
            category_namespace_name = namespace['name']
            category_namespace_case = namespace['case']
            break
    else:
        raise LookupError('No category namespace returned by MediaWiki API!')
    category_namespace_names = [category_namespace_name]
    if category_namespace_name != 'Category':
        category_namespace_names.append('Category')
    for namespacealias in response['query']['namespacealiases']:
        if namespacealias['id'] == category_namespace_id:
            category_namespace_names.append(namespacealias['alias'])
    category_info = (category_namespace_name, category_namespace_names, category_namespace_case)

    messages = {}
    for message in response['query']['allmessages']:
        messages[message['name']] = message['content']

    return (category_info, messages)


siteinfo_cache = cachetools.TTLCache(maxsize=1024, ttl=24*60*60)  # type: cachetools.TTLCache[str, _SiteInfo]
siteinfo_cache_lock = threading.RLock()


def category_info(session: mwapi.Session) -> CategoryInfo:
    with siteinfo_cache_lock:
        siteinfo = siteinfo_cache.get(session.host)
        if not siteinfo:
            siteinfo = _get_siteinfo(session)
            siteinfo_cache[session.host] = siteinfo
    return siteinfo[0]


def comma_separator(session: mwapi.Session) -> str:
    with siteinfo_cache_lock:
        siteinfo = siteinfo_cache.get(session.host)
        if not siteinfo:
            siteinfo = _get_siteinfo(session)
            siteinfo_cache[session.host] = siteinfo
    return siteinfo[1]['comma-separator']


def semicolon_separator(session: mwapi.Session) -> str:
    with siteinfo_cache_lock:
        siteinfo = siteinfo_cache.get(session.host)
        if not siteinfo:
            siteinfo = _get_siteinfo(session)
            siteinfo_cache[session.host] = siteinfo
    return siteinfo[1]['semicolon-separator']


def word_separator(session: mwapi.Session) -> str:
    with siteinfo_cache_lock:
        siteinfo = siteinfo_cache.get(session.host)
        if not siteinfo:
            siteinfo = _get_siteinfo(session)
            siteinfo_cache[session.host] = siteinfo
    return siteinfo[1]['word-separator']


def parentheses(session: mwapi.Session, content: str) -> str:
    with siteinfo_cache_lock:
        siteinfo = siteinfo_cache.get(session.host)
        if not siteinfo:
            siteinfo = _get_siteinfo(session)
            siteinfo_cache[session.host] = siteinfo
    return siteinfo[1]['parentheses'].replace('$1', content)
