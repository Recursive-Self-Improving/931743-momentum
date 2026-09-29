"""
A股动量轮动策略 - 配置
"""

# ========== 跟踪标的池 ==========
ETF_POOL = {
    # 宽基ETF
    "510300": {"name": "沪深300ETF", "category": "大盘价值"},
    "510500": {"name": "中证500ETF", "category": "中盘成长"},
    "588000": {"name": "科创50ETF", "category": "科技创新"},
    "159915": {"name": "创业板ETF", "category": "创业成长"},
    "512100": {"name": "中证1000ETF", "category": "小盘"},
    # 行业ETF
    "512480": {"name": "半导体ETF", "category": "科技"},
    "515030": {"name": "新能源ETF", "category": "新能源"},
    "512800": {"name": "银行ETF", "category": "金融"},
    "512010": {"name": "医药ETF", "category": "医药"},
    "515880": {"name": "通信ETF", "category": "通俠/AI"},
    "159995": {"name": "芯片ETF", "category": "芯片"},
    "516970": {"name": "基建ETF", "category": "基建/周期"},
}

# 避险标的
SAFE_HAVENS = {
    "511880": {"name": "银华日利货币基金", "category": "货币"},
    "511010": {"name": "国债ETF", "category": "债券"},
}

ALL_SYMBOLS = {**ETF_POOL, **SAFE_HAVENS}

# ========== 动量计算参数 ==========
MOMENTUM_WINDOWS = {
    5: 0.40,    # 5日动量权40%
    10: 0.30,   # 10日动量权30%
    20: 0.20,   # 20日动量权20%
    60: 0.10,   # 60日动量权10%
}

TREND_MA_PERIOD = 10       # 趋势确认均线周期
VOLATILITY_MA_PERIOD = 20  # 波动率计算周期
MAX_DAILY_VOLATILITY = 5.0 # 每日波动率上限%，超过降权

# ========== 持仓规则 ==========
MAX_HOLDINGS = 3           # 最多持有N只
HOLDING_TOLERANCE = 2      # 当前持仓在Top(N+2)内不换
MIN_MOMENTUM = -1.0        # 最小动量分，允许略微负动量（强者恒强，弱市也可持最强）
CLEAR_COOLDOWN_DAYS = 3    # 清仓后冷却N天，避免频繁进出

# ========== 风控参数 ==========
RISK_STRONG_PCT_WARNING = 0.35   # 动量>0的标的 < 35% → 预警
RISK_STRONG_PCT_EMERGENCY = 0.20  # < 20% → 清仓
RISK_MA_PCT_WARNING = 0.25      # 价在MA上方的 < 25% → 预警
RISK_MA_PCT_EMERGENCY = 0.10    # < 10% → 清仓
RISK_MOM_DECLINE_DAYS = 5       # 平均动量连续下降N天 → 降仓
RISK_MOM_DECLINE_CUTOFF = 0.50  # 降仓50%

# ========== 数据参数 ==========
HISTORY_DAYS = 120          # 回测历史数据天数
DATA_DELAY_MINUTES = 15     # akshare延迟（实际无延迟，先取数据验证）

# ========== 交易参数 ==========
TRADE_TIME = "14:50"      # 每日执行时间（接近收盘，给足下单时间）
EXECUTION_BUFFER = 0.001   # 卖单滑点缓冲（0.1%）

# ========== 回测参数 ==========
INITIAL_CAPITAL = 100000   # 初始资金
COMMISSION_RATE = 0.0003   # 万三手续费（0.03%）
SLIPPAGE = 0.001          # 滑点（0.1%），每次交易买卖各算一次
