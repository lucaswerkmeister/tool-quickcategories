import siteinfo


class FakeSession:

    def __init__(self, response):
        self.response = response

    def get(self, *args, **kwargs):
        return self.response


def test_category_info_enwiki():
    response = {
        'query': {
            'namespaces': {
                # ...
                '14': {
                    'id': 14,
                    'name': 'Category',
                    'canonical': 'Category',
                },
                '15': {
                    'id':15,
                    'name': 'Category talk',
                    'canonical': 'Category talk',
                },
                # ...
            },
            'namespacealiases': [
                # ...
            ],
        },
    }
    session = FakeSession(response)
    category_info = siteinfo.category_info(session)
    assert category_info == ('Category', ['Category'])

def test_category_info_dewiki():
    response = {
        'query': {
            'namespaces': {
                # ...
                '14': {
                    'id': 14,
                    'name': 'Kategorie',
                    'canonical': 'Category',
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
        },
    }
    session = FakeSession(response)
    category_info = siteinfo.category_info(session)
    assert category_info == ('Kategorie', ['Kategorie', 'Category'])

def test_category_info_ruwiki():
    response = {
        'query': {
            'namespaces': {
                # ...
                '14': {
                    'id': 14,
                    'name': 'Категория',
                    'canonical': 'Category',
                },
                '15': {
                    'id':15,
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
        },
    }
    session = FakeSession(response)
    category_info = siteinfo.category_info(session)
    assert category_info == ('Категория', ['Категория', 'Category', 'К'])
