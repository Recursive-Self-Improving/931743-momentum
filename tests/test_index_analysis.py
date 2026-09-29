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
from src.index_data import Candle
from src.index_strategy import IndexStrategy
from src.risk_controller import RiskController


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


@pytest.mark.parametrize('last_close', [100.0, 100.001, 1000.0])
def test_entry_requires_positive_adjusted_score_and_strict_trend(last_close):
    decision = IndexStrategy().decide(
        pd.DataFrame({'close': [100.0] * 79 + [last_close]}), invested=False,
    )
    # Flat prices, rounding to zero, and a zero volatility factor all forbid entry.
    assert decision['action'] == 'clear_all'
    assert decision['target_weight'] == 0.0


def test_decline_requires_five_strictly_decreasing_scores_and_clear_takes_priority():
    risk = RiskController()
    for momentum in (5.0, 4.0, 3.0, 2.0):
        assert risk.analyze(momentum, True)['warning'] is False
    assert risk.analyze(1.0, True)['warning'] is True
    assert risk.analyze(1.0, True)['warning'] is False  # A tie breaks the decline.

    strategy = IndexStrategy()
    prices = [100.0 + i for i in range(80)]
    for last_close in (200.0, 195.0, 190.0, 185.0, 180.0):
        decision = strategy.decide(pd.DataFrame({'close': prices[:-1] + [last_close]}), invested=True)
    assert decision['action'] == 'reduce_half'
    assert decision['target_weight'] == pytest.approx(1 / 3)
    decision = strategy.decide(pd.DataFrame({'close': prices[:-1] + [100.0]}), invested=True)
    assert decision['signals']['risk']['warning'] is True
    assert decision['action'] == 'clear_all'
    assert decision['target_weight'] == 0.0


def test_healthy_hold_keeps_units_and_allows_weight_to_drift():
    candles = candles_for([100.0] * 70 + [110.0 + 2 * i for i in range(20)])
    result = analyze_history(candles, start=candles[70].date)
    assert len(result['trades']) == 1
    assert result['trades'][0]['side'] == 'buy'
    latest = result['daily'][-1]
    assert latest['effective_action'] == 'hold'
    assert latest['actual_weight'] > 1 / 3
    assert latest['index_units'] == result['trades'][0]['units']
