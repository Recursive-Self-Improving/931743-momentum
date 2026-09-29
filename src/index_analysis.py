"""Replay 931743 close signals with next-session open execution."""

from dataclasses import asdict
from datetime import date

import pandas as pd

from src import config
from src.index_data import Candle
from src.index_strategy import IndexStrategy

# Keep the previous analysis origin fixed; daily updates must not drop old signals.
SIGNAL_START = date(2024, 9, 29)


def _round_trips(trades: list[dict], session_numbers: dict[str, int]) -> list[dict]:
    result = []
    entry = None
    for trade in trades:
        if trade['side'] == 'buy':
            if entry is None:
                entry = {
                    'entry_signal_date': trade['signal_date'],
                    'entry_date': trade['execution_date'],
                    'entry_open': trade['open_price'],
                    'cost': 0.0, 'units': 0.0, 'buy_fills': 0,
                }
            entry['cost'] -= trade['cash_flow']
            entry['units'] += trade['units']
            entry['buy_fills'] += 1
        else:
            profit = trade['cash_flow'] - entry['cost']
            result.append({
                **entry,
                'exit_signal_date': trade['signal_date'],
                'exit_date': trade['execution_date'],
                'exit_open': trade['open_price'],
                'proceeds': trade['cash_flow'],
                'pnl': profit,
                'net_return_pct': profit / entry['cost'] * 100,
                'holding_sessions': session_numbers[trade['execution_date']] - session_numbers[entry['entry_date']],
            })
            entry = None
    return result


def analyze_history(candles: list[Candle], *, start: date = SIGNAL_START) -> dict:
    """Close decisions execute only at the following returned session's open.

    Warm risk/cooldown state on pre-window data, but start the measured account in
    cash. Preserve original 1/3 sizing, hold drift, warning-driven top-ups and
    repeated-clear cooldown resets. Fractional index units are research only.
    """
    warmup = max(config.MOMENTUM_WINDOWS) + 5
    if sum(c.date < start for c in candles) < warmup:
        raise ValueError(f'历史预热不足：信号起点前至少需要 {warmup} 根日线。')
    if not candles or candles[-1].date < start:
        raise ValueError('行情尚未覆盖固定信号起点，无法生成报告。')

    frame = pd.DataFrame([asdict(c) for c in candles])
    strategy = IndexStrategy()
    cash = float(config.INITIAL_CAPITAL)
    units = 0.0
    pending = None
    last_clear = None
    previous_equity = cash
    peak_equity = cash
    daily, trades, events = [], [], []

    for i, candle in enumerate(candles):
        day, opening, closing = candle.date, candle.open, candle.close
        day_text = day.isoformat()
        in_window = day >= start
        open_value = cash + units * opening
        fee_today = slip_today = 0.0
        if pending and pending['action'] == 'clear_all':
            # A clear instruction resets cooldown even when already in cash.
            last_clear = day
        if in_window and pending and pending['action'] != 'hold':
            target = pending['target_weight']
            fill = None
            if units > 0 and (pending['action'] == 'clear_all' or target == 0):
                quantity = units
                fill_price = opening * (1 - config.SLIPPAGE)
                notional = quantity * fill_price
                fee_today = notional * config.COMMISSION_RATE
                slip_today = quantity * opening * config.SLIPPAGE
                cash_flow = notional - fee_today
                cash += cash_flow
                units = 0.0
                side, kind = 'sell', 'sell'
                fill = True
            elif target > 0:
                fill_price = opening * (1 + config.SLIPPAGE)
                quantity = open_value * target / fill_price - units
                if quantity > 1e-10:
                    notional = quantity * fill_price
                    fee = notional * config.COMMISSION_RATE
                    if cash >= notional + fee:
                        side, kind = 'buy', 'buy' if units == 0 else 'add'
                        fee_today = fee
                        slip_today = quantity * opening * config.SLIPPAGE
                        cash_flow = -notional - fee
                        cash += cash_flow
                        units += quantity
                        fill = True
            event = pending.get('event')
            if fill:
                trade = {
                    'signal_date': pending['signal_date'], 'execution_date': day_text,
                    'side': side, 'units': quantity, 'open_price': opening,
                    'fill_price': fill_price, 'notional': notional,
                    'commission': fee_today, 'slippage_cost': slip_today,
                    'cash_flow': cash_flow, 'source_action': pending['action'],
                }
                trades.append(trade)
                # A pre-window close can instruct the first in-window open.
                if event is None:
                    event = pending['event_record'].copy()
                    events.append(event)
                event.update(kind=kind, status='executed', execution_date=day_text,
                             execution_open=opening, fill_price=fill_price,
                             units=quantity, cash_flow=cash_flow)
            elif event is not None:
                event.update(status='no_fill', execution_date=day_text,
                             execution_open=opening)

        equity = cash + units * closing
        if i + 1 < warmup:
            continue
        actual_weight = units * closing / equity
        snapshot = frame.iloc[:i + 1]
        decision = strategy.decide(snapshot, invested=units > 0)
        raw_action = decision['action']
        cooldown = last_clear is not None and (day - last_clear).days < config.CLEAR_COOLDOWN_DAYS
        blocked = cooldown and raw_action not in ('hold', 'clear_all')
        if blocked:
            decision = {'action': 'hold', 'target_weight': 0.0,
                        'signals': decision['signals']}
        score = decision['signals']['score']
        risk = decision['signals']['risk']
        reasons = '; '.join(risk['reasons'])
        target = decision['target_weight']
        action = decision['action']
        if blocked:
            kind = 'cooldown'
        elif action == 'clear_all':
            kind = 'sell' if units > 0 else 'flat'
        elif action == 'reduce_half' and target > 0:
            kind = 'rebalance_check'
        elif action == 'rebalance' and target > 0:
            kind = 'buy' if units == 0 else 'rebalance_check'
        else:
            kind = 'hold' if units > 0 else 'flat'

        event_record = {
            'signal_date': day_text, 'kind': kind, 'status': 'pending',
            'execution_date': None, 'signal_close': closing,
            'execution_open': None, 'fill_price': None, 'units': None,
            'cash_flow': None, 'source_action': action,
            'reason': reasons or '动量与均线条件通过',
        }
        event = None
        if in_window and kind in ('buy', 'sell', 'rebalance_check'):
            event = event_record
            events.append(event)
        if in_window:
            peak_equity = max(peak_equity, equity)
            daily.append({
                'date': day_text, 'open': opening, 'high': candle.high,
                'low': candle.low, 'close': closing,
                **{f'return_{w}d_pct': (closing / candles[i - w].close - 1) * 100
                   for w in config.MOMENTUM_WINDOWS},
                'ma10': float(snapshot['close'].iloc[-config.TREND_MA_PERIOD:].mean()),
                'mean_abs_return_20d_pct': float(snapshot['close'].pct_change().iloc[-config.VOLATILITY_MA_PERIOD:].abs().mean() * 100),
                'raw_momentum': float(score['raw_momentum']),
                'adjusted_momentum': float(score['adjusted_momentum']),
                'volatility_penalty': float(score['volatility_penalty']),
                'trend_ok': bool(score['trend_ok']),
                'risk_emergency': bool(risk['emergency']),
                'risk_warning': bool(risk['warning']),
                'momentum_declining': bool(risk['mom_declining']),
                'risk_reasons': reasons, 'raw_action': raw_action,
                'effective_action': action, 'cooldown_active': cooldown,
                'cooldown_blocked': blocked,
                'last_clear_execution_date': last_clear.isoformat() if last_clear else None,
                'target_weight': target, 'actual_weight': actual_weight,
                'cash': cash, 'index_units': units, 'portfolio_value': equity,
                'daily_return': equity / previous_equity - 1,
                'drawdown': equity / peak_equity - 1,
                'commission': fee_today, 'slippage_cost': slip_today,
                'signal_kind': kind,
            })
            previous_equity = equity
        pending = {**decision, 'signal_date': day_text, 'event': event,
                   'event_record': event_record}

    counts = {kind: sum(e['kind'] == kind and e['status'] == 'executed' for e in events)
              for kind in ('buy', 'add', 'sell')}
    return {
        'summary': {
            'day_count': len(daily), 'buy_count': counts['buy'],
            'add_count': counts['add'], 'sell_count': counts['sell'],
            'pending_count': sum(e['status'] == 'pending' for e in events),
            'final_value': daily[-1]['portfolio_value'],
            'position_weight': daily[-1]['actual_weight'],
            'total_return_pct': (daily[-1]['portfolio_value'] / config.INITIAL_CAPITAL - 1) * 100,
            'latest_signal': daily[-1]['signal_kind'],
        },
        'daily': daily, 'trades': trades, 'events': events,
        'round_trips': _round_trips(trades, {c.date.isoformat(): i for i, c in enumerate(candles)}),
    }
