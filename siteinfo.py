import mwapi # type: ignore
from typing import List, Tuple


def category_info(session: mwapi.Session) -> Tuple[str, List[str]]:
    """Return the primary name of the category namespace and all the names
    with which a category link may be formed."""
    response = session.get(action='query',
                           meta='siteinfo',
                           siprop=['namespaces', 'namespacealiases'],
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
    return category_namespace_name, category_namespace_names


def comma_separator(session: mwapi.Session) -> str:
    return session.get(action='query',
                       meta='allmessages',
                       ammessages='comma-separator',
                       formatversion=2)['query']['allmessages'][0]['content']


def parentheses(session: mwapi.Session, content: str) -> str:
    return session.get(action='query',
                       meta='allmessages',
                       ammessages='parentheses',
                       amargs=content,
                       formatversion=2)['query']['allmessages'][0]['content']
