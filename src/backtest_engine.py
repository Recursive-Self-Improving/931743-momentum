"""
回测引擎
- 日线级别回测
- T+1模拟（当日买入，次日可用）
- 手续费、滑点模拟
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from src.config import INITIAL_CAPITAL, COMMISSION_RATE, SLIPPAGE, CLEAR_COOLDOWN_DAYS
from src.rotation_strategy import RotationStrategy
from src.risk_controller import RiskController


class BacktestEngine:
    """ETF轮动策略回测"""

    def __init__(
        self,
        symbols: Dict[str, dict],
        start_date: str,
        end_date: str,
        initial_capital: float = INITIAL_CAPITAL,
        commission: float = COMMISSION_RATE,
        slippage: float = SLIPPAGE,
    ):
        self.symbols = symbols
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

        self.capital = initial_capital
        self.holdings = {}  # {symbol: shares}
        self.cash = initial_capital
        self.history = []   # 每日记录
        self.trades = []    # 交易记录
        self.last_clear_date = None  # 上次清仓日期

    def run(self, data_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        执行回测
        data_dict: 所有标的的历史数据
        返回每日权益曲线
        """
        # 1. 对齐所有日期
        all_dates = set()
        for df in data_dict.values():
            dates = set(df['日期'].dt.date)
            all_dates |= dates

        trade_dates = sorted([d for d in all_dates
                             if self.start_date.date() <= d <= self.end_date.date()])

        if len(trade_dates) < 20:
            print("❌ 交易日不足，无法回测")
            return pd.DataFrame()

        # 2. 初始化策略
        rc = RiskController()
        strategy = RotationStrategy(rc)

        # 3. 逐日模拟
        for i, date in enumerate(trade_dates):
            date_str = date.strftime('%Y-%m-%d')

            # 构建当日可用的数据快照（截止到当日）
            snapshot = {}
            for symbol, df in data_dict.items():
                day_df = df[df['日期'].dt.date <= date]
                if len(day_df) >= 20:
                    snapshot[symbol] = day_df.copy()

            if len(snapshot) < 3:
                continue

            # 计算当前持仓市值
            portfolio_value = self.cash
            for sym, shares in self.holdings.items():
                price = self._get_price(data_dict, sym, date, '收盘')
                if price:
                    portfolio_value += shares * price

            # 当前持仓比例
            holding_ratios = {}
            if portfolio_value > 0:
                for sym, shares in self.holdings.items():
                    price = self._get_price(data_dict, sym, date, '收盘')
                    if price:
                        holding_ratios[sym] = (shares * price) / portfolio_value

            cash_ratio = self.cash / portfolio_value if portfolio_value > 0 else 1.0

            # 策略决策
            decision = strategy.decide(
                snapshot,
                current_holdings=holding_ratios,
                current_cash=cash_ratio,
            )

            # 冷却期检查：清仓后N天内不入场
            if self.last_clear_date is not None:
                days_since_clear = (date - self.last_clear_date).days
                if days_since_clear < CLEAR_COOLDOWN_DAYS:
                    # 强制持有现金，不买任何东西
                    if decision['action'] not in ('hold', 'clear_all'):
                        decision = {
                            'action': 'hold',
                            'target_holdings': {},
                            'target_cash': 1.0,
                            'signals': decision['signals'],
                        }

            # 执行交易（T+1: 如果当日已买入，当日不能卖出）
            # 回测简化：收盘决策，次日开盘价执行（或收盘价执行）
            # 这里用收盘价近似，假设有足够时间下单
            self._execute(decision, data_dict, date, portfolio_value)
            strategy.update_holdings(
                {sym: (shares * self._get_price(data_dict, sym, date, '收盘') / portfolio_value)
                 for sym, shares in self.holdings.items()
                 if self._get_price(data_dict, sym, date, '收盘')},
                self.cash / portfolio_value if portfolio_value > 0 else 1.0
            )

            # 记录
            risk_signals = decision['signals'].get('risk', {})
            self.history.append({
                'date': date,
                'portfolio_value': portfolio_value,
                'cash': self.cash,
                'holdings': list(self.holdings.keys()),
                'action': decision['action'],
                'risk_warning': risk_signals.get('warning', False),
                'risk_emergency': risk_signals.get('emergency', False),
            })

        df_result = pd.DataFrame(self.history)
        if len(df_result) == 0:
            return df_result

        df_result['daily_return'] = df_result['portfolio_value'].pct_change()
        df_result['cum_return'] = (df_result['portfolio_value'] / self.initial_capital - 1) * 100
        df_result['max_drawdown'] = (df_result['portfolio_value'] / df_result['portfolio_value'].cummax() - 1) * 100

        return df_result

    def _get_price(self, data_dict, symbol, date, field='收盘'):
        """获取某标某日的价格"""
        df = data_dict.get(symbol)
        if df is None:
            return None
        row = df[df['日期'].dt.date == date]
        if len(row) == 0:
            return None
        return float(row[field].iloc[-1])

    def _execute(self, decision, data_dict, date, portfolio_value):
        """执行交易决策"""
        target = decision['target_holdings']
        action = decision['action']

        if action == 'hold':
            return

        # 清仓
        if action == 'clear_all':
            for sym in list(self.holdings.keys()):
                price = self._get_price(data_dict, sym, date, '收盘')
                if price:
                    shares = self.holdings[sym]
                    # 卖出价 = 收盘价 * (1 - 滑点)
                    exec_price = price * (1 - self.slippage)
                    proceeds = shares * exec_price
                    fee = proceeds * self.commission
                    self.cash += proceeds - fee
                    self.trades.append({
                        'date': date,
                        'symbol': sym,
                        'action': 'sell',
                        'shares': shares,
                        'price': exec_price,
                        'fee': fee,
                    })
            self.holdings.clear()
            self.last_clear_date = date  # 记录清仓日期
            return

        # 目标持仓转换为股数
        target_shares = {}
        for sym, weight in target.items():
            target_value = portfolio_value * weight
            price = self._get_price(data_dict, sym, date, '收盘')
            if price:
                # 买入价 = 收盘价 * (1 + 滑点)
                exec_price = price * (1 + self.slippage)
                shares = int(target_value / exec_price)
                if shares > 0:
                    target_shares[sym] = shares

        # 先卖后买
        current_set = set(self.holdings.keys())
        target_set = set(target_shares.keys())

        # 卖出不在目标中的
        for sym in current_set - target_set:
            price = self._get_price(data_dict, sym, date, '收盘')
            if price and sym in self.holdings:
                shares = self.holdings[sym]
                exec_price = price * (1 - self.slippage)
                proceeds = shares * exec_price
                fee = proceeds * self.commission
                self.cash += proceeds - fee
                del self.holdings[sym]
                self.trades.append({
                    'date': date,
                    'symbol': sym,
                    'action': 'sell',
                    'shares': shares,
                    'price': exec_price,
                    'fee': fee,
                })

        # 买入目标中不足或新增的
        for sym, target_sh in target_shares.items():
            current_sh = self.holdings.get(sym, 0)
            if target_sh > current_sh:
                need = target_sh - current_sh
                price = self._get_price(data_dict, sym, date, '收盘')
                if price:
                    exec_price = price * (1 + self.slippage)
                    cost = need * exec_price
                    fee = cost * self.commission
                    total_cost = cost + fee
                    if self.cash >= total_cost:
                        self.cash -= total_cost
                        self.holdings[sym] = current_sh + need
                        self.trades.append({
                            'date': date,
                            'symbol': sym,
                            'action': 'buy',
                            'shares': need,
                            'price': exec_price,
                            'fee': fee,
                        })

    def stats(self, df_result: pd.DataFrame) -> Dict:
        """计算回测统计"""
        if len(df_result) == 0:
            return {}

        total_return = (df_result['portfolio_value'].iloc[-1] / self.initial_capital - 1) * 100
        annual_return = total_return / (len(df_result) / 252)
        max_dd = df_result['max_drawdown'].min()
        volatility = df_result['daily_return'].std() * np.sqrt(252) * 100

        # 夏普（简化，假设无风险利率0）
        sharpe = annual_return / volatility if volatility > 0 else 0

        # 胜率
        win_days = len(df_result[df_result['daily_return'] > 0])
        total_days = len(df_result[df_result['daily_return'] != 0])
        win_rate = win_days / total_days * 100 if total_days > 0 else 0

        # 交易次数
        trade_count = len(self.trades)

        return {
            'total_return': round(total_return, 2),
            'annual_return': round(annual_return, 2),
            'max_drawdown': round(max_dd, 2),
            'volatility': round(volatility, 2),
            'sharpe': round(sharpe, 2),
            'win_rate': round(win_rate, 2),
            'trade_count': trade_count,
            'final_value': round(df_result['portfolio_value'].iloc[-1], 2),
        }
