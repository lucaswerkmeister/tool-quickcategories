import mwapi # type: ignore
from typing import Dict, List, Tuple


CategoryInfo = Tuple[str, List[str]]
"""The primary name of the category namespace
and all the names with which a category link may be formed."""


_SiteInfo = Tuple[CategoryInfo, Dict[str, str]]
"""The category info,
and a dict from message key to message content."""


def _get_siteinfo(session: mwapi.Session) -> _SiteInfo:
    response = session.get(action='query',
                           meta=['siteinfo', 'allmessages'],
                           siprop=['namespaces', 'namespacealiases'],
                           ammessages=['comma-separator', 'parentheses'],
                           formatversion=2)

    for namespace in response['query']['namespaces'].values():
        if namespace.get('canonical') == 'Category':
            category_namespace_id = namespace['id']
            category_namespace_name = namespace['name']
            break
    else:
        raise LookupError('No category namespace returned by MediaWiki API!')
    category_namespace_names  = [category_namespace_name]
    if category_namespace_name != 'Category':
        category_namespace_names.append('Category')
    for namespacealias in response['query']['namespacealiases']:
        if namespacealias['id'] == category_namespace_id:
            category_namespace_names.append(namespacealias['alias'])
    category_info = (category_namespace_name, category_namespace_names)

    messages = {}
    for message in response['query']['allmessages']:
        messages[message['name']] = message['content']

    return (category_info, messages)


def category_info(session: mwapi.Session) -> CategoryInfo:
    return _get_siteinfo(session)[0]


def comma_separator(session: mwapi.Session) -> str:
    return _get_siteinfo(session)[1]['comma-separator']


def parentheses(session: mwapi.Session, content: str) -> str:
    return _get_siteinfo(session)[1]['parentheses'].replace('$1', content)
