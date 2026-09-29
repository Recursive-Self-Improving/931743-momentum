#!/usr/bin/env python3
"""
回测运行脚本
- 获取历史数据
- 运行回测
- 输出统计报告
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import datetime, timedelta
from src.config import ETF_POOL, SAFE_HAVENS, ALL_SYMBOLS
from src.data_provider import DataProvider
from src.backtest_engine import BacktestEngine


def run():
    print("════════════════════════════════════════════")
    print("    A股ETF动量轮动策略 - 回测")
    print("════════════════════════════════════════════")

    # 1. 获取数据
    dp = DataProvider()
    print("\n📊 正在获取历史数据...")
    all_data = dp.fetch_all(ALL_SYMBOLS, days=250)

    print(f"\n✅ 成功获取 {len(all_data)} 只ETF数据")
    for sym, df in all_data.items():
        name = ALL_SYMBOLS.get(sym, {}).get('name', sym)
        print(f"   {sym} ({name}): {len(df)} 条记录, 日期范围 {df['日期'].min().date()} ~ {df['日期'].max().date()}")

    if len(all_data) < 5:
        print("❌ 数据不足，无法回测")
        return

    # 2. 运行回测
    # 回测周期：近半年
    end = datetime.now()
    start = end - timedelta(days=180)

    print(f"\n🔄 回测周期: {start.date()} ~ {end.date()}")

    bt = BacktestEngine(
        symbols=ALL_SYMBOLS,
        start_date=start.strftime('%Y-%m-%d'),
        end_date=end.strftime('%Y-%m-%d'),
    )

    result = bt.run(all_data)

    if len(result) == 0:
        print("❌ 回测无结果")
        return

    # 3. 统计
    stats = bt.stats(result)

    print("\n" + "═"*50)
    print("📊 回测统计结果")
    print("═"*50)
    print(f"  总收益率:    {stats['total_return']:+.2f}%")
    print(f"  年化收益:    {stats['annual_return']:+.2f}%")
    print(f"  最大回撤:    {stats['max_drawdown']:+.2f}%")
    print(f"  波动率:      {stats['volatility']:.2f}%")
    print(f"  夏普比:      {stats['sharpe']:.2f}")
    print(f"  日胜率:      {stats['win_rate']:.1f}%")
    print(f"  交易次数:    {stats['trade_count']}")
    print(f"  最终资金:    ¥{stats['final_value']:,.2f}")
    print("═"*50)

    # 4. 每日持仓展示
    print("\n📅 最近30日持仓变化:")
    recent = result.tail(30)
    for _, row in recent.iterrows():
        date = row['date'].strftime('%m-%d')
        val = row['portfolio_value']
        ret = row['daily_return'] * 100 if pd.notna(row['daily_return']) else 0
        holdings = ', '.join(row['holdings']) if row['holdings'] else '空仓'
        action = row['action']
        emoji = ''
        if action == 'clear_all':
            emoji = '🚨'
        elif action == 'reduce_half':
            emoji = '⚠️'
        elif action == 'rebalance':
            emoji = '🔄'
        print(f"  {date} | {val:>10,.0f} | {ret:>+5.2f}% | {emoji} {holdings}")

    # 5. 风控触发记录
    risk_events = result[result['risk_emergency'] | result['risk_warning']]
    if len(risk_events) > 0:
        print(f"\n🚨 风控事件 ({len(risk_events)} 次):")
        for _, row in risk_events.iterrows():
            date = row['date'].strftime('%Y-%m-%d')
            if row['risk_emergency']:
                print(f"  ❌ {date} - 清仓!")
            else:
                print(f"  ⚠️ {date} - 预警")

    # 6. 保存结果
    result.to_csv('~/a股动量轮动策略/data/backtest_result.csv', index=False)
    print("\n✅ 详细结果已保存到 data/backtest_result.csv")

    # 7. 对比持有沪深300
    print("\n📊 与沪深300对比:")
    df_300 = all_data.get('510300')
    if df_300 is not None:
        bt_period = df_300[(df_300['日期'].dt.date >= start.date()) & (df_300['日期'].dt.date <= end.date())]
        if len(bt_period) > 0:
            buyhold_return = (bt_period['收盘'].iloc[-1] / bt_period['收盘'].iloc[0] - 1) * 100
            print(f"  买入持有沪深300: {buyhold_return:+.2f}%")
            print(f"  本策略:         {stats['total_return']:+.2f}%")
            print(f"  超额收益:       {stats['total_return'] - buyhold_return:+.2f}%")


if __name__ == '__main__':
    run()
