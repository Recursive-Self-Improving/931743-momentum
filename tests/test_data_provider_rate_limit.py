import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_provider import DataProvider


def test_fetch_history_reuses_cache_when_latest_trade_date_is_today(monkeypatch, tmp_path):
    today = pd.Timestamp.today().normalize()
    cached = pd.DataFrame({'日期': [today], '收盘': [1.23]})
    cache_file = tmp_path / '510300_120d.pkl'
    cached.to_pickle(cache_file)

    def forbidden_fetch(*args, **kwargs):
        raise AssertionError('fresh cache should not hit remote source')

    monkeypatch.setattr('src.data_provider.ak.fund_etf_hist_em', forbidden_fetch)

    provider = DataProvider(cache_dir=str(tmp_path))
    result = provider.fetch_history('510300', days=120)

    pd.testing.assert_frame_equal(result, cached)


def test_fetch_history_retries_with_exponential_backoff(monkeypatch, tmp_path):
    attempts = []
    sleeps = []

    def fake_fetch(*args, **kwargs):
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError('remote disconnected')
        return pd.DataFrame({'日期': ['2026-05-25'], '收盘': [2.0]})

    monkeypatch.setattr('src.data_provider.ak.fund_etf_hist_em', fake_fetch)
    monkeypatch.setattr('src.data_provider.time.sleep', lambda seconds: sleeps.append(seconds))

    provider = DataProvider(cache_dir=str(tmp_path))
    result = provider.fetch_history('510300', days=120, use_cache=False)

    assert len(attempts) == 3
    assert sleeps == [1.0, 2.0]
    assert result['收盘'].iloc[0] == 2.0


def test_fetch_all_sleeps_with_jitter_between_symbols(monkeypatch, tmp_path):
    sleeps = []
    jitter_values = iter([0.1, 0.2])

    def fake_fetch_history(self, symbol, days=120, adjust='qfq', use_cache=True):
        return pd.DataFrame({'日期': pd.date_range('2026-05-01', periods=20), '收盘': range(20)})

    monkeypatch.setattr('src.data_provider.DataProvider.fetch_history', fake_fetch_history)
    monkeypatch.setattr('src.data_provider.random.uniform', lambda a, b: next(jitter_values))
    monkeypatch.setattr('src.data_provider.time.sleep', lambda seconds: sleeps.append(seconds))

    provider = DataProvider(cache_dir=str(tmp_path))
    result = provider.fetch_all({'510300': {}, '510500': {}, '588000': {}}, days=120)

    assert list(result.keys()) == ['510300', '510500', '588000']
    assert sleeps == [1.6, 1.7]
