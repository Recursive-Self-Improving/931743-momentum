"""
轮动策略核心
- 解析动量排名 + 风控信号 → 交易决策
"""

import pandas as pd
from typing import Dict, List, Tuple
from src.config import (
    MAX_HOLDINGS, HOLDING_TOLERANCE, MIN_MOMENTUM,
    ETF_POOL, SAFE_HAVENS,
)
from src.momentum_engine import MomentumEngine
from src.risk_controller import RiskController


class RotationStrategy:
    """根据动量轮动的策略"""

    def __init__(
        self,
        risk_controller: RiskController = None,
        *,
        universe: Dict[str, dict] = None,
    ):
        self.universe = ETF_POOL if universe is None else universe
        self.rc = risk_controller or RiskController(universe=self.universe)
        self.holdings = {}  # 当前持仓: {symbol: weight}
        self.cash_ratio = 0.0

    def decide(
        self,
        data_dict: Dict[str, pd.DataFrame],
        current_holdings: Dict[str, float] = None,
        current_cash: float = 0.0,
    ) -> Dict:
        """
        主决策函数

        data_dict: 所有标的的历史数据
        current_holdings: 当前持仓比例 {symbol: ratio}
        current_cash: 当前现金比例

        返回: {
            'action': 'hold' | 'rebalance' | 'clear_all' | 'reduce_half',
            'target_holdings': {symbol: ratio},
            'target_cash': float,
            'signals': {...}
        }
        """
        if current_holdings is not None:
            self.holdings = current_holdings.copy()
        self.cash_ratio = current_cash

        # 1. 计算所有标的动量
        rank_df = MomentumEngine.rank_all(data_dict)
        if rank_df.empty:
            return {
                'action': 'hold',
                'target_holdings': self.holdings,
                'target_cash': self.cash_ratio,
                'signals': {'error': '无数据'},
            }

        # 2. 风控分析
        risk = self.rc.analyze(data_dict, rank_df)

        # 3. 根据风控决定大体操作
        if risk['emergency']:
            return {
                'action': 'clear_all',
                'target_holdings': {},
                'target_cash': 1.0,
                'signals': {
                    'rank': rank_df.to_dict('records'),
                    'risk': risk,
                }
            }

        if risk['warning'] and risk['action'] == 'reduce_half':
            # 降仓50%，只保留最强的1只（如果有）
            target = self._build_target(rank_df, max_slots=1, data_dict=data_dict)
            # 其余转现金
            if target:
                total_weight = sum(target.values())
                cash = 1.0 - total_weight
            else:
                cash = 1.0
            return {
                'action': 'reduce_half',
                'target_holdings': target,
                'target_cash': cash,
                'signals': {
                    'rank': rank_df.to_dict('records'),
                    'risk': risk,
                }
            }

        # 4. 正常情况：构建目标持仓
        target = self._build_target(rank_df, max_slots=MAX_HOLDINGS, data_dict=data_dict)

        # 5. 是否需要调仓
        action = self._decide_action(target)

        total_weight = sum(target.values())
        cash = 1.0 - total_weight

        return {
            'action': action,
            'target_holdings': target,
            'target_cash': cash,
            'signals': {
                'rank': rank_df.to_dict('records'),
                'risk': risk,
                'holdings': list(self.holdings.keys()),
                'target': list(target.keys()),
            }
        }

    def _build_target(
        self,
        rank_df: pd.DataFrame,
        max_slots: int,
        data_dict: Dict[str, pd.DataFrame],
    ) -> Dict[str, float]:
        """构建目标持仓 {symbol: weight}"""
        # 只从股票池子中选，避险标的只有在清仓时被动持有
        eligible = rank_df[rank_df['symbol'].isin(self.universe)]

        # 只要过趋势确认的才考虑
        eligible = eligible[eligible['pass_filter'] == True]

        # 只要动量分正的
        eligible = eligible[eligible['adjusted_momentum'] > MIN_MOMENTUM]

        # 取Top max_slots
        top = eligible.head(max_slots)

        if len(top) == 0:
            return {}

        # 等权分配
        weight_per = 1.0 / MAX_HOLDINGS  # 按最大持仓数分配，不是按实际拥有数
        target = {}
        for _, row in top.iterrows():
            target[row['symbol']] = weight_per

        return target

    def _decide_action(self, target: Dict[str, float]) -> str:
        """判断是否需要调仓"""
        current_set = set(self.holdings.keys())
        target_set = set(target.keys())

        # 完全一致，不动
        if current_set == target_set:
            return 'hold'

        # 检查是否可以少动（当前持仓在Top N+2内）
        if current_set:
            # 允许当前持仓在较宽范围内，避免频繁调仓
            return 'rebalance'

        return 'rebalance'

    def update_holdings(self, holdings: Dict[str, float], cash: float):
        """更新当前持仓状态"""
        self.holdings = holdings.copy()
        self.cash_ratio = cash
