"""931743 自身的动量、均线与连续下降判断，不推断全市场广度。"""

from src.config import RISK_MOM_DECLINE_DAYS


class RiskController:
    """跨交易日保留调整后动量，用于连续下降判断。"""

    def __init__(self):
        self.momentum_history = []

    def analyze(self, adjusted_momentum: float, trend_ok: bool) -> dict:
        self.momentum_history.append(adjusted_momentum)
        if len(self.momentum_history) > RISK_MOM_DECLINE_DAYS:
            self.momentum_history.pop(0)
        declining = len(self.momentum_history) == RISK_MOM_DECLINE_DAYS and all(
            current < previous
            for previous, current in zip(self.momentum_history, self.momentum_history[1:])
        )

        # 单指数下，原池子的强者/均线多头比例只能为0或1。
        # 所有非正动量或未通过MA10的日线均触发清仓，而非广度预警。
        emergency = adjusted_momentum <= 0 or not trend_ok
        reasons = []
        if adjusted_momentum <= 0:
            reasons.append(f'调整后动量{adjusted_momentum:.2f}不大于0')
        if not trend_ok:
            reasons.append('收盘价未高于趋势均线')
        if declining:
            reasons.append(f'最近{RISK_MOM_DECLINE_DAYS}次调整后动量严格递减')

        return {
            'emergency': emergency,
            'warning': declining,
            'mom_declining': declining,
            'reasons': reasons,
        }
