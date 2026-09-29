"""Behavioral boundaries for the official CSI candle parser (no network)."""

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.index_data import Candle, DataError, HISTORY_START, parse_candles


def row(day="20230719", **changes):
    values = {
        "indexCode": "931743",
        "tradeDate": day,
        "open": "101.5",
        "high": "103",
        "low": "100",
        "close": "102",
        "tradingVol": "1234",
        "tradingValue": "1.25",
    }
    values.update(changes)
    return values


def test_parses_unsorted_rows_and_converts_yi_to_yuan():
    payload = {"code": 200, "data": [row("20230720", tradingValue="0"), row()]}

    candles = parse_candles(payload, HISTORY_START, date(2023, 7, 20))

    assert candles == [
        Candle(HISTORY_START, 101.5, 103.0, 100.0, 102.0, 1234.0, 125_000_000.0),
        Candle(date(2023, 7, 20), 101.5, 103.0, 100.0, 102.0, 1234.0, 0.0),
    ]


@pytest.mark.parametrize(
    'rows',
    [
        [row(indexCode='000001')],
        [row('20230720')],
        [row(), row()],
        [row('20230722')],
        [row('20230718')],
        [row('20230721')],
    ],
)
def test_rejects_wrong_identity_or_date_coverage(rows):
    with pytest.raises(DataError):
        parse_candles({'code': '200', 'data': rows}, HISTORY_START, date(2023, 7, 20))


@pytest.mark.parametrize(
    'payload',
    [
        None,
        {'code': 500, 'data': [row()]},
        {'code': 200, 'data': None},
        {'code': 200, 'data': []},
        {'code': 200, 'data': [None]},
        {'code': 200, 'data': [row(tradeDate='not-a-date')]},
        {'code': 200, 'data': [row(high=None)]},
        {'code': 200, 'data': [{'indexCode': '931743'}]},
    ],
)
def test_malformed_payload_is_data_error(payload):
    with pytest.raises(DataError):
        parse_candles(payload, HISTORY_START, HISTORY_START)


@pytest.mark.parametrize(
    'change',
    [
        {'open': 'nan'},
        {'tradingVol': 'inf'},
        {'tradingValue': '1e308'},
        {'low': '0'},
        {'high': '101'},
        {'low': '102.5'},
        {'tradingVol': '-1'},
        {'tradingValue': '-0.1'},
    ],
)
def test_rejects_invalid_ohlc_and_turnover(change):
    with pytest.raises(DataError):
        parse_candles({'code': 200, 'data': [row(**change)]}, HISTORY_START, HISTORY_START)
