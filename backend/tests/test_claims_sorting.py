import pytest


from app.utils.sorting import parse_sort_params


def test_parse_sort_params_single():
    res = parse_sort_params('amount', 'asc')
    assert res == [('amount', 'asc')]


def test_parse_sort_params_multi_paired():
    res = parse_sort_params('amount,created_at', 'asc,desc')
    assert res == [('amount', 'asc'), ('created_at', 'desc')]


def test_parse_sort_params_multi_single_dir():
    res = parse_sort_params('amount,created_at', 'asc')
    assert res == [('amount', 'asc'), ('created_at', 'asc')]


def test_parse_sort_params_invalid_dir():
    res = parse_sort_params('amount,claim_id', 'up,down')
    assert res == [('amount', 'desc'), ('claim_id', 'desc')]


def test_parse_sort_params_none():
    res = parse_sort_params(None, None)
    assert res == [('created_at', 'desc')]
