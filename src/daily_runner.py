"""
每日运行器
- 收盘后获取最新数据
- 计算信号
- 生成交易建议
- 发送通知
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional

from src.config import ALL_SYMBOLS, ETF_POOL, SAFE_HAVENS
from src.data_provider import DataProvider
from src.momentum_engine import MomentumEngine
from src.risk_controller import RiskController
from src.rotation_strategy import RotationStrategy


class DailyRunner:
    """每日策略运行"""

    def __init__(self, cache_dir: str = None):
        self.dp = DataProvider(cache_dir)
        self.rc = RiskController()
        self.strategy = RotationStrategy(self.rc)

    def run(self, current_holdings: Dict[str, float] = None, current_cash: float = 0.0) -> Dict:
        """
        执行每日分析

        current_holdings: 当前持仓比例 {symbol: ratio}
        current_cash: 当前现金比例

        返回完整分析报告
        """
        print(f"\n{'='*60}")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} 策略日报")
        print(f"{'='*60}")

        # 1. 获取数据
        print("\n📊 获取ETF历史数据...")
        all_data = self.dp.fetch_all(ALL_SYMBOLS, days=120)

        if len(all_data) < 5:
            return {'error': '数据不足', 'action': 'hold'}

        # 2. 计算动量排名
        rank_df = MomentumEngine.rank_all(all_data)
        print(f"\n🏆 ETF动量排名（Top 10）：")
        top10 = rank_df.head(10)
        for _, row in top10.iterrows():
            sym = row['symbol']
            name = ALL_SYMBOLS.get(sym, {}).get('name', sym)
            mom = row['adjusted_momentum']
            trend = '✅' if row['trend_ok'] else '❌'
            print(f"   {row['rank']:>2}. {sym} {name:<12} | 动量: {mom:>+6.2f}% | 趋势{trend}")

        # 3. 风控分析
        risk = self.rc.analyze(all_data, rank_df)
        print(f"\n🛡️ 风控状态：")
        if risk['emergency']:
            print(f"   🚨 EMERGENCY! 清仓信号！")
        elif risk['warning']:
            print(f"   ⚠️ WARNING! 降低仓位！")
        else:
            print(f"   ✅ 正常")

        metrics = risk['metrics']
        print(f"   强标占比: {metrics['strong_pct']*100:.0f}%")
        print(f"   均线上方: {metrics['ma_bull_pct']*100:.0f}%")
        print(f"   平均动量: {metrics['avg_momentum']:+.2f}%")

        if risk['reasons']:
            for r in risk['reasons']:
                print(f"   ⚡ {r}")

        # 4. 策略决策
        decision = self.strategy.decide(
            all_data,
            current_holdings=current_holdings,
            current_cash=current_cash,
        )

        print(f"\n📋 交易决策：")
        action_map = {
            'hold': '持仓不动',
            'rebalance': '调仓换股',
            'reduce_half': '减仓50%',
            'clear_all': '清仓避险',
        }
        action_desc = action_map.get(decision['action'], decision['action'])
        print(f"   动作: {action_desc}")

        target = decision['target_holdings']
        if target:
            print(f"   目标持仓:")
            for sym, weight in target.items():
                name = ALL_SYMBOLS.get(sym, {}).get('name', sym)
                print(f"     {sym} {name} ({weight*100:.0f}%)")
        else:
            print(f"   目标持仓: 空仓")

        print(f"   现金比例: {decision['target_cash']*100:.0f}%")

        # 5. 如果当前有持仓，对比建议
        if current_holdings:
            print(f"\n📊 当前 vs 目标：")
            current_set = set(current_holdings.keys())
            target_set = set(target.keys())
            to_sell = current_set - target_set
            to_buy = target_set - current_set
            keep = current_set & target_set

            if to_sell:
                for sym in to_sell:
                    name = ALL_SYMBOLS.get(sym, {}).get('name', sym)
                    print(f"   🔴 卖出 {sym} {name}")
            if to_buy:
                for sym in to_buy:
                    name = ALL_SYMBOLS.get(sym, {}).get('name', sym)
                    print(f"   🟢 买入 {sym} {name}")
            if keep:
                for sym in keep:
                    name = ALL_SYMBOLS.get(sym, {}).get('name', sym)
                    print(f"   🟡 持有 {sym} {name}")

        return decision

    def generate_report(self, decision: Dict) -> str:
        """生成可读的交易报告"""
        lines = []
        lines.append(f"📅 {datetime.now().strftime('%Y-%m-%d')} ETF动量轮动日报")
        lines.append("")

        rank = decision['signals']['rank']
        risk = decision['signals']['risk']

        lines.append("🏆 动量排名Top5:")
        for i, row in enumerate(rank[:5], 1):
            sym = row['symbol']
            name = ALL_SYMBOLS.get(sym, {}).get('name', sym)
            lines.append(f"  {i}. {sym} {name} | {row['adjusted_momentum']:+.2f}%")

        lines.append("")
        lines.append("🛡️ 风控:")
        if risk['emergency']:
            lines.append("  🚨 清仓信号！")
        elif risk['warning']:
            lines.append("  ⚠️ 预警！")
        else:
            lines.append("  ✅ 正常")

        lines.append("")
        action = decision['action']
        lines.append(f"📋 决策: {action}")
        if decision['target_holdings']:
            for sym, w in decision['target_holdings'].items():
                name = ALL_SYMBOLS.get(sym, {}).get('name', sym)
                lines.append(f"  → {sym} {name} {w*100:.0f}%")
        else:
            lines.append("  → 空仓")

        return "\n".join(lines)


if __name__ == '__main__':
    runner = DailyRunner()
    # 模拟当前持仓为空
    result = runner.run(current_holdings={}, current_cash=1.0)
    print(f"\n{'='*60}")
    print("📧 交易通知文本：")
    print(f"{'='*60}")
    print(runner.generate_report(result))
