import siteinfo

from test_utils import FakeSession


response_enwiki = {
    'query': {
        'namespaces': {
            # ...
            '14': {
                'id': 14,
                'name': 'Category',
                'canonical': 'Category',
                'case': 'first-letter',
            },
            '15': {
                'id': 15,
                'name': 'Category talk',
                'canonical': 'Category talk',
            },
            # ...
        },
        'namespacealiases': [
            # ...
        ],
        'allmessages': [
            {
                "name": "comma-separator",
                "content": ", ",
            },
            {
                "name": "semicolon-separator",
                "content": "; ",
            },
            {
                "name": "parentheses",
                "content": "($1)",
            },
        ],
    },
}
response_dewiktionary = {
    'query': {
        'namespaces': {
            # ...
            '14': {
                'id': 14,
                'name': 'Kategorie',
                'canonical': 'Category',
                'case': 'case-sensitive',
            },
            '15': {
                'id': 15,
                'name': 'Kategorie Diskussion',
                'canonical': 'Category talk',
            },
            # ...
        },
        'namespacealiases': [
            # ...
        ],
        'allmessages': [
            {
                "name": "comma-separator",
                "content": ", ",
            },
            {
                "name": "semicolon-separator",
                "content": "; ",
            },
            {
                "name": "parentheses",
                "content": "($1)",
            },
        ],
    },
}
response_ruwiki = {
    'query': {
        'namespaces': {
            # ...
            '14': {
                'id': 14,
                'name': 'Категория',
                'canonical': 'Category',
                'case': 'first-letter',
            },
            '15': {
                'id': 15,
                'name': 'Обсуждение категории',
                'canonical': 'Category talk',
            },
            # ...
        },
        'namespacealiases': [
            # ...
            {
                'id': 14,
                'alias': 'К',
            },
            # ...
        ],
        'allmessages': [
            {
                "name": "comma-separator",
                "content": ", ",
            },
            {
                "name": "semicolon-separator",
                "content": "; ",
            },
            {
                "name": "parentheses",
                "content": "($1)",
            },
        ],
    },
}
response_zhwiki = {
    'query': {
        'namespaces': {
            # ...
            '14': {
                'id': 14,
                'name': 'Category',
                'canonical': 'Category',
                'case': 'first-letter',
            },
            '15': {
                'id': 15,
                'name': 'Category talk',
                'canonical': 'Category talk',
            },
            # ...
        },
        'namespacealiases': [
            # ...
            {
                'id': 14,
                'alias': 'CAT',
            },
            {
                'id': 14,
                'alias': '分类',
            },
            {
                'id': 14,
                'alias': '分類',
            },
            # ...
        ],
        'allmessages': [
            {
                'name': 'comma-separator',
                'content': '、 ',
            },
            {
                "name": "semicolon-separator",
                "content": "；",
            },
            {
                'name': 'parentheses',
                'content': '（$1）',
            },
        ],
    },
}


def test_category_info_enwiki():
    session = FakeSession(response_enwiki)
    session.host = 'https://en.wikipedia.org'
    category_info = siteinfo.category_info(session)
    assert category_info == ('Category', ['Category'], 'first-letter')

def test_category_info_dewiktionary():
    session = FakeSession(response_dewiktionary)
    session.host = 'https://de.wiktionary.org'
    category_info = siteinfo.category_info(session)
    assert category_info == ('Kategorie', ['Kategorie', 'Category'], 'case-sensitive')

def test_category_info_ruwiki():
    session = FakeSession(response_ruwiki)
    session.host = 'https://ru.wikipedia.org'
    category_info = siteinfo.category_info(session)
    assert category_info == ('Категория', ['Категория', 'Category', 'К'], 'first-letter')


def test_comma_separator():
    session = FakeSession(response_zhwiki)
    session.host = 'https://zh.wikipedia.org'
    comma_separator = siteinfo.comma_separator(session)
    assert comma_separator == '、 '


def test_semicolon_separator():
    session = FakeSession(response_zhwiki)
    session.host = 'https://zh.wikipedia.org'
    semicolon_separator = siteinfo.semicolon_separator(session)
    assert semicolon_separator == '；'


def test_parentheses():
    session = FakeSession(response_zhwiki)
    session.host = 'https://zh.wikipedia.org'
    parentheses = siteinfo.parentheses(session, 'foo')
    assert parentheses == '（foo）'
