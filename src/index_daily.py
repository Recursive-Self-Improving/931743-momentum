"""Fresh 931743 close signals and a self-contained GitHub Pages artifact.

Run from the repository root: python -m src.index_daily --output site
"""

import argparse
import csv
import io
import json
import sys
from dataclasses import asdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from src import config
from src.index_analysis import SIGNAL_START, analyze_history
from src.index_data import DataError, HISTORY_START, INDEX_CODE, INDEX_NAME, SOURCE_URL, fetch_candles
from src.index_report import render_html

SHANGHAI = ZoneInfo('Asia/Shanghai')
CLOSE_CUTOFF = time(15, 30)
TRADE_FIELDS = ['signal_date', 'execution_date', 'side', 'units', 'open_price',
                'fill_price', 'notional', 'commission', 'slippage_cost',
                'cash_flow', 'source_action']
EVENT_FIELDS = ['signal_date', 'kind', 'status', 'execution_date', 'signal_close',
                'execution_open', 'fill_price', 'units', 'cash_flow',
                'source_action', 'reason']
ROUND_TRIP_FIELDS = ['entry_signal_date', 'entry_date', 'entry_open', 'cost',
                     'units', 'buy_fills', 'exit_signal_date', 'exit_date',
                     'exit_open', 'proceeds', 'pnl', 'net_return_pct', 'holding_sessions']


def request_dates(as_of: date | None, now: datetime) -> tuple[date, date]:
    local = now.astimezone(SHANGHAI)
    requested = as_of or local.date()
    if requested > local.date():
        raise ValueError('截止日期不可晚于北京时间今天。')
    completed = local.date() if local.time() >= CLOSE_CUTOFF else local.date() - timedelta(days=1)
    end = min(requested, completed)
    if end < SIGNAL_START:
        raise ValueError(f'截止日期尚未覆盖固定信号起点 {SIGNAL_START}。')
    return requested, end


def data_status(requested: date, latest: date, now: datetime) -> tuple[str, str]:
    local = now.astimezone(SHANGHAI)
    if requested < local.date():
        return 'historical', f'历史回溯至 {requested}；最后可用日线为 {latest}。'
    if local.weekday() < 5 and local.time() < CLOSE_CUTOFF:
        return 'awaiting_close', f'北京时间 15:30 前排除今日 K 线；最新完整日线为 {latest}，不是今日收盘判断。'
    if latest < requested:
        return 'no_current_bar', f'未取得 {requested} 的完整日线，可能休市或源数据尚未发布；最新为 {latest}，不等于今日无信号。'
    return 'current', f'已获取 {latest} 的完整日线；信号在收盘确认，最早下一交易日开盘执行。'


def _csv_text(rows: list[dict], fields: list[str]) -> str:
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def generate_report(output: Path, as_of: date | None = None) -> dict:
    now = datetime.now(SHANGHAI)
    requested, end = request_dates(as_of, now)
    # Full replay is intentional: no previous Actions runner state is required.
    candles = fetch_candles(HISTORY_START, end)
    analysis = analyze_history(candles)
    status, message = data_status(requested, candles[-1].date, now)
    report = {
        'index_code': INDEX_CODE, 'index_name': INDEX_NAME,
        'generated_at': now.isoformat(), 'requested_as_of': requested.isoformat(),
        'data_status': status, 'status_message': message,
        'history_start': candles[0].date.isoformat(),
        'signal_start': SIGNAL_START.isoformat(),
        'first_signal_date': analysis['daily'][0]['date'],
        'latest_date': candles[-1].date.isoformat(),
        'source_url': SOURCE_URL + '?' + urlencode({
            'indexCode': INDEX_CODE, 'startDate': HISTORY_START.strftime('%Y%m%d'),
            'endDate': end.strftime('%Y%m%d'),
        }),
        'parameters': {
            'momentum_weights': {str(k): v for k, v in config.MOMENTUM_WINDOWS.items()},
            'trend_ma': config.TREND_MA_PERIOD,
            'volatility_window': config.VOLATILITY_MA_PERIOD,
            'volatility_threshold_pct': config.MAX_DAILY_VOLATILITY,
            'max_holdings': config.MAX_HOLDINGS,
            'cooldown_calendar_days': config.CLEAR_COOLDOWN_DAYS,
            'initial_capital': config.INITIAL_CAPITAL,
            'commission_per_side': config.COMMISSION_RATE,
            'slippage_per_side': config.SLIPPAGE,
        },
        **analysis,
    }
    ohlc = [{**asdict(c), 'date': c.date.isoformat()} for c in candles]
    # Fetch, replay and render must all succeed before replacing any output.
    files = {
        'index.html': render_html(report),
        'summary.json': json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
        'daily_signals.csv': _csv_text(report['daily'], list(report['daily'][0])),
        'trades.csv': _csv_text(report['trades'], TRADE_FIELDS),
        'events.csv': _csv_text(report['events'], EVENT_FIELDS),
        'round_trips.csv': _csv_text(report['round_trips'], ROUND_TRIP_FIELDS),
        'ohlc_history.csv': _csv_text(ohlc, list(ohlc[0])),
        '.nojekyll': '',
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (output / name).write_text(content, encoding='utf-8')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='更新 931743 动量信号并生成完整历史 HTML 报告')
    parser.add_argument('--output', type=Path, default=Path('site'), help='输出目录，默认 site/')
    parser.add_argument('--as-of', type=date.fromisoformat, help='历史截止日 YYYY-MM-DD；默认北京时间今天')
    args = parser.parse_args()
    try:
        report = generate_report(args.output, args.as_of)
    except (DataError, ValueError, OSError) as error:
        print(f'报告生成失败：{error}；不发布旧数据作为本次更新。', file=sys.stderr)
        return 1
    summary = report['summary']
    labels = {'buy': '买入，待下一交易日开盘', 'sell': '清仓，待下一交易日开盘',
              'rebalance_check': '下一交易日检查 1/3 目标仓位', 'hold': '继续持有',
              'flat': '保持现金', 'cooldown': '冷却期拦截，保持现金'}
    print(f"{INDEX_CODE} {INDEX_NAME}")
    print(f"数据状态：{report['data_status']} | {report['status_message']}")
    print(f"历史范围：{report['first_signal_date']}—{report['latest_date']}，{summary['day_count']} 个交易日")
    print(f"最新收盘信号：{labels[summary['latest_signal']]}；模拟实际仓位 {summary['position_weight']:.2%}")
    print(f"历史模拟成交：建仓 {summary['buy_count']}、补买 {summary['add_count']}、卖出 {summary['sell_count']}；待执行检查 {summary['pending_count']}")
    print(f"HTML：{args.output / 'index.html'}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
