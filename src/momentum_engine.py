"""
动量计算引擎
- 多周期动量加权
- 趋势确认
- 波动率惩罚
"""

import pandas as pd
from typing import Dict, Optional
from src.config import (
    MOMENTUM_WINDOWS, TREND_MA_PERIOD, VOLATILITY_MA_PERIOD,
    MAX_DAILY_VOLATILITY
)


class MomentumEngine:
    """计算单只标的动量分数"""

    @staticmethod
    def calculate_momentum(df: pd.DataFrame) -> Optional[float]:
        """
        计算动量分
        df需要包含列: close
        返回综合动量分，或None（数据不足）
        """
        if len(df) < max(MOMENTUM_WINDOWS.keys()) + 5:
            return None

        close = df['close'].astype(float)

        momentum_score = 0.0
        for window, weight in MOMENTUM_WINDOWS.items():
            ret = (close.iloc[-1] / close.iloc[-(window + 1)] - 1) * 100
            momentum_score += ret * weight

        return momentum_score

    @staticmethod
    def trend_confirm(df: pd.DataFrame, period: int = TREND_MA_PERIOD) -> bool:
        """收盘价是否在均线之上，确保不是暴跌中的反弹"""
        if len(df) < period:
            return False
        close = df['close'].astype(float)
        ma = close.rolling(period).mean().iloc[-1]
        return close.iloc[-1] > ma

    @staticmethod
    def volatility_penalty(df: pd.DataFrame, max_vol: float = MAX_DAILY_VOLATILITY) -> float:
        """
        根据20日平均绝对日收益降低动量权重。
        返回一个惩罚系数 (0~1)，1表示无惩罚
        """
        if len(df) < VOLATILITY_MA_PERIOD:
            return 1.0

        close = df['close'].astype(float)
        daily_ret = close.pct_change() * 100
        avg_vol = daily_ret.abs().rolling(VOLATILITY_MA_PERIOD).mean().iloc[-1]

        if avg_vol <= max_vol:
            return 1.0
        # 波动率超过上限，线性降权
        penalty = max(0, 1 - (avg_vol - max_vol) / max_vol)
        return penalty

    @classmethod
    def score(cls, df: pd.DataFrame) -> Optional[Dict]:
        """
        返回完整的评分结果
        """
        mom = cls.calculate_momentum(df)
        if mom is None:
            return None

        trend = cls.trend_confirm(df)
        penalty = cls.volatility_penalty(df)
        adjusted_mom = mom * penalty

        return {
            'raw_momentum': round(mom, 2),
            'trend_ok': trend,
            'volatility_penalty': round(penalty, 2),
            'adjusted_momentum': round(adjusted_mom, 2),
        }
