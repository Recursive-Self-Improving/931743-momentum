"""931743 动量信号与假设性模拟参数。"""

# 多周期动量：收益率以百分数计。
MOMENTUM_WINDOWS = {
    5: 0.40,
    10: 0.30,
    20: 0.20,
    60: 0.10,
}
TREND_MA_PERIOD = 10
VOLATILITY_MA_PERIOD = 20
MAX_DAILY_VOLATILITY = 5.0  # 20日平均绝对日收益超过5%时惩罚动量。

# 保留历史报告的仓位口径，不改为单标的满仓。
TARGET_WEIGHT = 1 / 3
CLEAR_COOLDOWN_DAYS = 3  # 自然日；空仓清仓指令也重置执行日期。
RISK_MOM_DECLINE_DAYS = 5  # 最近5次评分严格递减，即4次相邻下降。

INITIAL_CAPITAL = 100000
COMMISSION_RATE = 0.0003  # 单边佣金0.03%。
SLIPPAGE = 0.001          # 单边滑点0.1%。
