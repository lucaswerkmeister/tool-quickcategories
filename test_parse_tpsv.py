import pytest

import parse_tpsv


@pytest.mark.parametrize('tpsv', [
    '''Page|+Category:Cat''',
    '''Page|+Category:Cat|-Category:Dog|+Category:Goat''',
    '''Page 1|+Category:Cat
Page 2|-Category:Dog''',
])
def test_parse_batch_roundtrip(tpsv):
    batch = parse_tpsv.parse_batch(tpsv)
    tpsv_ = str(batch)
    batch_ = parse_tpsv.parse_batch(tpsv_)
    assert batch == batch_

def test_parse_batch_skips_empty_lines():
    tpsv1 = '''

Page 1|+Category:Cat

Page 2|-Category:Dog

'''
    tpsv2 = 'Page 1|+Category:Cat\nPage 2|-Category:Dog'
    assert parse_tpsv.parse_batch(tpsv1) == parse_tpsv.parse_batch(tpsv2)

def test_parse_batch_strips_whitespace():
    tpsv1 = '  Page 1 |    +Category:Cat '
    tpsv2 = 'Page 1|+Category:Cat'
    assert parse_tpsv.parse_batch(tpsv1) == parse_tpsv.parse_batch(tpsv2)

def test_parse_batch_supports_crlf():
    tpsv1 = 'Page 1|+Category:Cat\r\nPage 2|-Category:Dog'
    tpsv2 = 'Page 1|+Category:Cat\nPage 2|-Category:Dog'
    assert parse_tpsv.parse_batch(tpsv1) == parse_tpsv.parse_batch(tpsv2)

def test_parse_batch_supports_tabs():
    tpsv1 = 'Page 1\t+Category:Cat\t-Category:Dog'
    tpsv2 = 'Page 1|+Category:Cat|-Category:Dog'
    assert parse_tpsv.parse_batch(tpsv1) == parse_tpsv.parse_batch(tpsv2)
