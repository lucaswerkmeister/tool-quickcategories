import pytest
from typing import Optional, TypedDict

import parse_tpsv


@pytest.mark.parametrize('tpsv', [
    '''Page|+Category:Cat''',
    '''Page|+Category:Cat|-Category:Dog|+Category:Goat''',
    '''Page 1|+Category:Cat
Page 2|-Category:Dog''',
    '''Page|+Category:Cat#sort key''',
    '''Page|+Category:Cat##sort key''',
    '''Page|+Category:Cat###sort key''',
    '''Page|+Category:Cat#''',
    '''Page|+Category:Cat##''',
    '''Page|+Category:Cat###''',
    '''Page|+Category:Cat#sort key with # embedded hash''',
    '''Page|+Category:Cat##sort key with # embedded hash''',
    '''Page|+Category:Cat###sort key with # embedded hash''',
    '''Redirect#resolve_redirects=no|+Category:Cat''',
    '''Redirect#resolve_redirects=no|+Category:Cat
No Redirect#resolve_redirects=yes|+Category:Dog''',
    '''Missing#create_missing_page=yes|+Category:Cat
Existing#create_missing_page=no|+Category:Dog''',
])
@pytest.mark.parametrize('default_resolve_redirects', [True, False])
@pytest.mark.parametrize('default_create_missing_page', [True, False])
def test_parse_batch_roundtrip(tpsv: str, default_resolve_redirects: bool, default_create_missing_page: bool) -> None:
    batch = parse_tpsv.parse_batch(tpsv,
                                   title=None,
                                   default_resolve_redirects=default_resolve_redirects,
                                   default_create_missing_page=default_create_missing_page)
    tpsv_ = str(batch)
    batch_ = parse_tpsv.parse_batch(tpsv_,
                                    title=None,
                                    default_resolve_redirects=default_resolve_redirects,
                                    default_create_missing_page=default_create_missing_page)
    assert batch == batch_

@pytest.mark.parametrize('default_resolve_redirects', [True, False])
@pytest.mark.parametrize('default_create_missing_page', [True, False])
def test_parse_batch_flags_defaults(default_resolve_redirects: bool, default_create_missing_page: bool) -> None:
    tpsv = '''
A|+Category:Cat
B#resolve_redirects=yes|+Category:Cat
C#resolve_redirects=no|+Category:Cat
D#create_missing_page=yes|+Category:Cat
E#create_missing_page=no|+Category:Cat
'''.strip()
    batch = parse_tpsv.parse_batch(tpsv,
                                   title=None,
                                   default_resolve_redirects=default_resolve_redirects,
                                   default_create_missing_page=default_create_missing_page)
    [page_A, page_B, page_C, page_D, page_E] = [command.page for command in batch.commands]
    assert page_A.resolve_redirects is default_resolve_redirects
    assert page_A.create_missing_page is default_create_missing_page
    assert page_B.resolve_redirects is True
    assert page_B.create_missing_page is default_create_missing_page
    assert page_C.resolve_redirects is False
    assert page_C.create_missing_page is default_create_missing_page
    assert page_D.resolve_redirects is default_resolve_redirects
    assert page_D.create_missing_page is True
    assert page_E.resolve_redirects is default_resolve_redirects
    assert page_E.create_missing_page is False

class IrrelevantParams(TypedDict):
    title: Optional[str]
    default_resolve_redirects: bool
    default_create_missing_page: bool

irrelevant_params: IrrelevantParams = {'title': None, 'default_resolve_redirects': True, 'default_create_missing_page': False}

def test_parse_batch_skips_empty_lines() -> None:
    tpsv1 = '''

Page 1|+Category:Cat

Page 2|-Category:Dog

'''
    tpsv2 = 'Page 1|+Category:Cat\nPage 2|-Category:Dog'
    assert parse_tpsv.parse_batch(tpsv1, **irrelevant_params) == parse_tpsv.parse_batch(tpsv2, **irrelevant_params)

def test_parse_batch_strips_whitespace() -> None:
    tpsv1 = '  Page 1 |    +Category:Cat '
    tpsv2 = 'Page 1|+Category:Cat'
    assert parse_tpsv.parse_batch(tpsv1, **irrelevant_params) == parse_tpsv.parse_batch(tpsv2, **irrelevant_params)

def test_parse_batch_supports_crlf() -> None:
    tpsv1 = 'Page 1|+Category:Cat\r\nPage 2|-Category:Dog'
    tpsv2 = 'Page 1|+Category:Cat\nPage 2|-Category:Dog'
    assert parse_tpsv.parse_batch(tpsv1, **irrelevant_params) == parse_tpsv.parse_batch(tpsv2, **irrelevant_params)

def test_parse_batch_supports_tabs() -> None:
    tpsv1 = 'Page 1\t+Category:Cat\t-Category:Dog'
    tpsv2 = 'Page 1|+Category:Cat|-Category:Dog'
    assert parse_tpsv.parse_batch(tpsv1, **irrelevant_params) == parse_tpsv.parse_batch(tpsv2, **irrelevant_params)

def test_parse_batch_preserves_title() -> None:
    tpsv = 'Page|+Category:Cat'
    batch = parse_tpsv.parse_batch(tpsv,
                                   title='Test title',
                                   default_resolve_redirects=True,
                                   default_create_missing_page=False)
    assert batch.title == 'Test title'
