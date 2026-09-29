from datetime import date, timedelta
from pathlib import Path
import sys

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import config
from src.index_analysis import analyze_history
from src.index_data import Candle, INDEX_CODE
from src.rotation_strategy import RotationStrategy


def candles_for(closes):
    days = []
    day = date(2024, 1, 1)
    while len(days) < len(closes):
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return [Candle(day, price, price, price, price, 100.0, 10000.0)
            for day, price in zip(days, closes)]


def test_close_signal_waits_for_next_open_and_books_the_open_gap():
    candles = candles_for([100.0] * 70 + [110.0 + 2 * i for i in range(10)] + [90.0] * 8)
    day = candles[81].date
    candles[81] = Candle(day, 80.0, 90.0, 80.0, 90.0, 100.0, 10000.0)
    start = candles[70].date
    before_entry = analyze_history(candles[:74], start=start)
    assert before_entry['trades'] == []
    pending_buy = before_entry['events'][-1]
    assert (pending_buy['kind'], pending_buy['status']) == ('buy', 'pending')
    assert pending_buy['signal_date'] == candles[73].date.isoformat()
    assert pending_buy['execution_date'] is None
    assert pending_buy['fill_price'] is None

    result = analyze_history(candles, start=start)
    buy, sell = result['trades'][0], result['trades'][-1]
    assert buy['execution_date'] == candles[74].date.isoformat()
    assert buy['units'] == pytest.approx(config.INITIAL_CAPITAL / 3 / (candles[74].open * 1.001))
    assert sell['signal_date'] == candles[80].date.isoformat()
    assert sell['execution_date'] == candles[81].date.isoformat()
    assert sell['fill_price'] == pytest.approx(80.0 * 0.999)
    assert result['daily'][10]['index_units'] > 0  # Sell signal close: still invested.
    assert result['daily'][11]['index_units'] == 0  # Following open: sold.
    assert result['summary']['final_value'] == pytest.approx(
        config.INITIAL_CAPITAL + sum(t['cash_flow'] for t in result['trades']))

    before_exit = analyze_history(candles[:81], start=start)
    assert before_exit['events'][-1]['status'] == 'pending'
    assert before_exit['events'][-1]['kind'] == 'sell'
    assert before_exit['daily'] == result['daily'][:11]
    assert before_exit['trades'] == [t for t in result['trades'] if t['execution_date'] <= candles[80].date.isoformat()]


def test_cooldown_counts_calendar_days_and_repeated_flat_clears_reset_it():
    candles = candles_for([100.0] * 74 + [110.0, 112.0, 114.0, 116.0])
    result = analyze_history(candles, start=candles[70].date)
    friday = next(row for row in result['daily'] if row['date'] == candles[74].date.isoformat())
    monday = next(row for row in result['daily'] if row['date'] == candles[75].date.isoformat())
    assert candles[74].date.weekday() == 4
    assert friday['cooldown_blocked'] is True
    assert friday['last_clear_execution_date'] == friday['date']
    assert monday['cooldown_blocked'] is False
    assert monday['signal_kind'] == 'buy'
    assert result['trades'][0]['execution_date'] == candles[76].date.isoformat()


def test_explicit_index_universe_does_not_change_default_etf_decisions():
    frame = pd.DataFrame({'close': [100.0 + i for i in range(80)]})
    default = RotationStrategy()
    custom = RotationStrategy(universe={INDEX_CODE: {'name': 'index'}})
    selected = custom.decide({INDEX_CODE: frame})
    rejected = default.decide({INDEX_CODE: frame})
    assert selected['target_holdings'] == {INDEX_CODE: 1 / config.MAX_HOLDINGS}
    assert selected['signals']['risk']['metrics']['ma_bull_pct'] == 1.0
    assert rejected['target_holdings'] == {}
    assert rejected['signals']['risk']['emergency'] is True
    assert INDEX_CODE not in config.ETF_POOL
