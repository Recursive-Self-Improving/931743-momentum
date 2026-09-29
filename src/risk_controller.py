"""
风控核心：强弱分化监测
判断市场是否“变天”——强者减少、弱者大面积增加时清仓
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple
from src.config import (
    RISK_STRONG_PCT_WARNING, RISK_STRONG_PCT_EMERGENCY,
    RISK_MA_PCT_WARNING, RISK_MA_PCT_EMERGENCY,
    RISK_MOM_DECLINE_DAYS, RISK_MOM_DECLINE_CUTOFF,
    TREND_MA_PERIOD, MOMENTUM_WINDOWS,
    ETF_POOL, SAFE_HAVENS,
)
from src.momentum_engine import MomentumEngine


class RiskController:
    """监控整个市场池子的健康度"""

    def __init__(self, *, universe: Dict[str, dict] = None):
        self.universe = ETF_POOL if universe is None else universe
        self.avg_momentum_history = []  # 记录平均动量历史

    def analyze(self, data_dict: Dict[str, pd.DataFrame], rank_df: pd.DataFrame) -> Dict:
        """
        返回市场健康度分析
        """
        if rank_df.empty:
            return {'emergency': True, 'warning': True, 'reason': '无数据'}

        total = len(rank_df)
        if total == 0:
            return {'emergency': True, 'warning': True, 'reason': '无有效标的'}

        # 1. 强者的数量（动量>0）
        strong_count = len(rank_df[rank_df['adjusted_momentum'] > 0])
        strong_pct = strong_count / total

        # 2. 均线多头数量
        ma_bull_count = 0
        for symbol in self.universe:
            if symbol in data_dict:
                if MomentumEngine.trend_confirm(data_dict[symbol], period=TREND_MA_PERIOD):
                    ma_bull_count += 1
        ma_bull_pct = ma_bull_count / len(self.universe) if self.universe else 0

        # 3. 平均动量趋势
        avg_momentum = rank_df['adjusted_momentum'].mean()
        self.avg_momentum_history.append(avg_momentum)
        if len(self.avg_momentum_history) > 10:
            self.avg_momentum_history.pop(0)

        # 判断连续下降
        mom_declining = False
        if len(self.avg_momentum_history) >= RISK_MOM_DECLINE_DAYS:
            recent = self.avg_momentum_history[-RISK_MOM_DECLINE_DAYS:]
            mom_declining = all(recent[i] < recent[i-1] for i in range(1, len(recent)))

        # 判断清仓/预警
        emergency = False
        warning = False
        reasons = []
        action = 'hold'

        # 强者过少
        if strong_pct < RISK_STRONG_PCT_EMERGENCY:
            emergency = True
            reasons.append(f'强者仅占{strong_pct*100:.0f}%，低于{RISK_STRONG_PCT_EMERGENCY*100:.0f}%')
        elif strong_pct < RISK_STRONG_PCT_WARNING:
            warning = True
            reasons.append(f'强者仅占{strong_pct*100:.0f}%，低于{RISK_STRONG_PCT_WARNING*100:.0f}%')

        # 均线空头
        if ma_bull_pct < RISK_MA_PCT_EMERGENCY:
            emergency = True
            reasons.append(f'均线上方仅占{ma_bull_pct*100:.0f}%，低于{RISK_MA_PCT_EMERGENCY*100:.0f}%')
        elif ma_bull_pct < RISK_MA_PCT_WARNING:
            warning = True
            reasons.append(f'均线上方仅占{ma_bull_pct*100:.0f}%，低于{RISK_MA_PCT_WARNING*100:.0f}%')

        # 平均动量转负
        if avg_momentum < 0:
            emergency = True
            reasons.append(f'平均动量{avg_momentum:.2f}已转负')

        # 连续下降
        if mom_declining:
            warning = True
            reasons.append(f'平均动量连续{RISK_MOM_DECLINE_DAYS}日下降')

        # 决定动作
        if emergency:
            action = 'clear_all'
        elif warning:
            action = 'reduce_half'

        return {
            'emergency': emergency,
            'warning': warning,
            'action': action,
            'reasons': reasons,
            'metrics': {
                'strong_pct': round(strong_pct, 2),
                'ma_bull_pct': round(ma_bull_pct, 2),
                'avg_momentum': round(avg_momentum, 2),
                'mom_declining': mom_declining,
            }
        }

    def clear_history(self):
        """清空历史记录（比如新一轮回测开始时）"""
        self.avg_momentum_history.clear()
