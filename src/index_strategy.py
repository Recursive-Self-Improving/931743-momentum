"""931743 收盘决策；资金、成交与冷却状态由历史重放维护。"""

import pandas as pd

from src.config import TARGET_WEIGHT
from src.momentum_engine import MomentumEngine
from src.risk_controller import RiskController


class IndexStrategy:
    def __init__(self):
        self.risk_controller = RiskController()

    def decide(self, history: pd.DataFrame, *, invested: bool) -> dict:
        score = MomentumEngine.score(history)
        if score is None:
            raise ValueError('历史不足，无法计算动量。')
        risk = self.risk_controller.analyze(score['adjusted_momentum'], score['trend_ok'])
        if risk['emergency']:
            action, target = 'clear_all', 0.0
        elif risk['warning']:
            # 保留历史动作名；执行含义是检查1/3目标，并非减半。
            action, target = 'reduce_half', TARGET_WEIGHT
        else:
            # 持仓正常时不再平衡，保留实际仓位漂移。
            action, target = ('hold' if invested else 'rebalance'), TARGET_WEIGHT
        return {
            'action': action,
            'target_weight': target,
            'signals': {'score': score, 'risk': risk},
        }
