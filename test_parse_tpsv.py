import pytest

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
    '''!Redirect|+Category:Cat''',
    '''!Redirect|+Category:Cat
No Redirect|+Category:Dog''',
])
def test_parse_batch_roundtrip(tpsv: str) -> None:
    batch = parse_tpsv.parse_batch(tpsv, title=None)
    tpsv_ = str(batch)
    batch_ = parse_tpsv.parse_batch(tpsv_, title=None)
    assert batch == batch_

def test_parse_batch_skips_empty_lines() -> None:
    tpsv1 = '''

Page 1|+Category:Cat

Page 2|-Category:Dog

'''
    tpsv2 = 'Page 1|+Category:Cat\nPage 2|-Category:Dog'
    assert parse_tpsv.parse_batch(tpsv1, title=None) == parse_tpsv.parse_batch(tpsv2, title=None)

def test_parse_batch_strips_whitespace() -> None:
    tpsv1 = '  Page 1 |    +Category:Cat '
    tpsv2 = 'Page 1|+Category:Cat'
    assert parse_tpsv.parse_batch(tpsv1, title=None) == parse_tpsv.parse_batch(tpsv2, title=None)

def test_parse_batch_supports_crlf() -> None:
    tpsv1 = 'Page 1|+Category:Cat\r\nPage 2|-Category:Dog'
    tpsv2 = 'Page 1|+Category:Cat\nPage 2|-Category:Dog'
    assert parse_tpsv.parse_batch(tpsv1, title=None) == parse_tpsv.parse_batch(tpsv2, title=None)

def test_parse_batch_supports_tabs() -> None:
    tpsv1 = 'Page 1\t+Category:Cat\t-Category:Dog'
    tpsv2 = 'Page 1|+Category:Cat|-Category:Dog'
    assert parse_tpsv.parse_batch(tpsv1, title=None) == parse_tpsv.parse_batch(tpsv2, title=None)

def test_parse_batch_preserves_title() -> None:
    tpsv = 'Page|+Category:Cat'
    batch = parse_tpsv.parse_batch(tpsv, title='Test title')
    assert batch.title == 'Test title'
