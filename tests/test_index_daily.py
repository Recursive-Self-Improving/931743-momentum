from datetime import date, datetime, timezone
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.index_daily import data_status, generate_report, request_dates
from src.index_data import DataError


def test_shanghai_cutoff_excludes_intraday_bar_without_moving_requested_date():
    before = datetime(2026, 9, 29, 7, 29, tzinfo=timezone.utc)
    at_cutoff = datetime(2026, 9, 29, 7, 30, tzinfo=timezone.utc)
    assert request_dates(None, before) == (date(2026, 9, 29), date(2026, 9, 28))
    assert request_dates(None, at_cutoff) == (date(2026, 9, 29), date(2026, 9, 29))
    assert request_dates(date(2025, 12, 31), before) == (date(2025, 12, 31), date(2025, 12, 31))
    with pytest.raises(ValueError):
        request_dates(date(2026, 9, 30), before)


def test_missing_latest_bar_is_not_reported_as_current_or_no_signal():
    after_close = datetime(2026, 9, 29, 10, 0, tzinfo=timezone.utc)
    before_close = datetime(2026, 9, 29, 3, 0, tzinfo=timezone.utc)
    assert data_status(date(2026, 9, 29), date(2026, 9, 28), after_close)[0] == 'no_current_bar'
    assert data_status(date(2026, 9, 29), date(2026, 9, 29), after_close)[0] == 'current'
    assert data_status(date(2026, 9, 29), date(2026, 9, 28), before_close)[0] == 'awaiting_close'
    assert data_status(date(2026, 9, 28), date(2026, 9, 28), after_close)[0] == 'historical'


def test_failed_fresh_fetch_does_not_replace_previous_report(monkeypatch, tmp_path):
    report = tmp_path / 'index.html'
    report.write_text('previous successful report', encoding='utf-8')

    def unavailable(*args):
        raise DataError('source unavailable')

    monkeypatch.setattr('src.index_daily.fetch_candles', unavailable)
    with pytest.raises(DataError):
        generate_report(tmp_path)
    assert report.read_text(encoding='utf-8') == 'previous successful report'
    assert not (tmp_path / 'summary.json').exists()
