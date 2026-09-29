#!/usr/bin/env python3
"""
A股ETF动量轮动策略 - 主入口

用法:
  python main.py backtest          # 运行回测
  python main.py daily             # 每日收盘后运行，生成交易信号
  python main.py paper             # 模拟盘（生成交易建议但不真实执行）
"""

import sys
import os
import json
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import ALL_SYMBOLS, INITIAL_CAPITAL
from src.data_provider import DataProvider
from src.backtest_engine import BacktestEngine
from src.daily_runner import DailyRunner
from src.notifier import Notifier


def cmd_backtest(args):
    """运行回测"""
    dp = DataProvider()
    print("📊 正在获取历史数据...")
    all_data = dp.fetch_all(ALL_SYMBOLS, days=250)
    print(f"✅ 获取成功: {len(all_data)} 只ETF")

    end = datetime.now()
    start = end - timedelta(days=args.days)

    bt = BacktestEngine(
        symbols=ALL_SYMBOLS,
        start_date=start.strftime('%Y-%m-%d'),
        end_date=end.strftime('%Y-%m-%d'),
        initial_capital=args.capital,
    )

    result = bt.run(all_data)
    stats = bt.stats(result)

    print("\n" + "="*50)
    print("📊 回测统计")
    print("="*50)
    print(f"  总收益率:    {stats['total_return']:+.2f}%")
    print(f"  年化收益:    {stats['annual_return']:+.2f}%")
    print(f"  最大回撤:    {stats['max_drawdown']:+.2f}%")
    print(f"  波动率:      {stats['volatility']:.2f}%")
    print(f"  夏普比:      {stats['sharpe']:.2f}")
    print(f"  日胜率:      {stats['win_rate']:.1f}%")
    print(f"  交易次数:    {stats['trade_count']}")
    print(f"  最终资金:    ¥{stats['final_value']:,.2f}")
    print("="*50)

    # 对比沪深300
    df_300 = all_data.get('510300')
    if df_300 is not None:
        bt_period = df_300[(df_300['日期'].dt.date >= start.date()) & (df_300['日期'].dt.date <= end.date())]
        if len(bt_period) > 0:
            buyhold_return = (bt_period['收盘'].iloc[-1] / bt_period['收盘'].iloc[0] - 1) * 100
            print(f"\n  买入持有沪深300: {buyhold_return:+.2f}%")
            print(f"  本策略:         {stats['total_return']:+.2f}%")
            print(f"  超额收益:       {stats['total_return'] - buyhold_return:+.2f}%")

    # 发送回测报告
    notifier = Notifier()
    notifier.send_backtest_report(stats)

    # 保存结果
    result.to_csv(os.path.expanduser('~/a股动量轮动策略/data/backtest_result.csv'), index=False)
    print("\n✅ 详细结果已保存")

    return stats


def cmd_daily(args):
    """每日运行：生成交易信号"""
    # 读取当前持仓（如果有保存）
    holdings_file = os.path.expanduser('~/a股动量轮动策略/data/current_holdings.json')
    current_holdings = {}
    current_cash = 1.0
    if os.path.exists(holdings_file):
        with open(holdings_file, 'r') as f:
            state = json.load(f)
            current_holdings = state.get('holdings', {})
            current_cash = state.get('cash', 1.0)
        print(f"📁 读取当前持仓: {current_holdings}, 现金: {current_cash}")

    runner = DailyRunner()
    decision = runner.run(
        current_holdings=current_holdings,
        current_cash=current_cash,
    )

    # 生成报告
    report = runner.generate_report(decision)

    # 保存信号
    notifier = Notifier()
    filename = notifier.save_signal_to_file(report)

    # 发送通知
    is_emergency = decision['signals']['risk']['emergency']
    notifier.send_signal(decision, report, is_emergency=is_emergency)

    # 如果是模拟盘/实盘模式，更新持仓状态
    if args.mode in ('paper', 'live'):
        new_state = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'holdings': decision['target_holdings'],
            'cash': decision['target_cash'],
            'action': decision['action'],
        }
        with open(holdings_file, 'w') as f:
            json.dump(new_state, f, indent=2)
        print(f"\n✅ 持仓状态已更新: {new_state}")

    return decision


def main():
    parser = argparse.ArgumentParser(description='A股ETF动量轮动策略')
    subparsers = parser.add_subparsers(dest='command', help='子命令')

    # backtest
    p_backtest = subparsers.add_parser('backtest', help='运行回测')
    p_backtest.add_argument('--days', type=int, default=180, help='回测天数')
    p_backtest.add_argument('--capital', type=float, default=INITIAL_CAPITAL, help='初始资金')

    # daily
    p_daily = subparsers.add_parser('daily', help='每日收盘后运行')
    p_daily.add_argument('--mode', choices=['signal', 'paper', 'live'], default='signal',
                        help='signal=只发信号, paper=模拟盘更新持仓, live=实盘执行')

    args = parser.parse_args()

    if args.command == 'backtest':
        cmd_backtest(args)
    elif args.command == 'daily':
        cmd_daily(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
