"""
数据获取模块
- akshare获取ETF历史数据
- 本地缓存减少重复请求
"""

import os
import json
import pickle
import random
import time

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional
from src.config import ALL_SYMBOLS


class DataProvider:
    """ETF历史数据提供器"""

    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/a股动量轮动策略/data")
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _cache_path(self, symbol: str, days: int) -> str:
        return os.path.join(self.cache_dir, f"{symbol}_{days}d.pkl")

    def _load_cache_if_fresh_for_today(self, cache_file: str) -> Optional[pd.DataFrame]:
        """如果缓存已经覆盖最新交易日，就直接用，别没事找东方财富聊天。"""
        if not os.path.exists(cache_file):
            return None

        with open(cache_file, 'rb') as f:
            df = pickle.load(f)

        if df is None or len(df) == 0 or '日期' not in df.columns:
            return None

        latest_date = pd.to_datetime(df['日期']).max().date()
        today = datetime.now().date()
        # A股周末不开盘：周末运行时，周五缓存就算当天有效。
        if today.weekday() == 5:  # Saturday
            expected_latest = today - timedelta(days=1)
        elif today.weekday() == 6:  # Sunday
            expected_latest = today - timedelta(days=2)
        else:
            expected_latest = today

        if latest_date >= expected_latest:
            print(f"📦 {os.path.basename(cache_file)} 已覆盖最新交易日 {latest_date}，使用缓存")
            return df
        return None

    def _sleep_between_symbols(self):
        delay = 1.5 + random.uniform(0.0, 2.0)
        print(f"⏳ 请求间隔 {delay:.1f}s，别把东方财富薅秃")
        time.sleep(delay)

    def fetch_history(
        self,
        symbol: str,
        days: int = 120,
        adjust: str = "qfq",
        use_cache: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        获取单只ETF历史日线
        adjust: qfq=前复权
        """
        cache_file = self._cache_path(symbol, days)

        if use_cache:
            cached_df = self._load_cache_if_fresh_for_today(cache_file)
            if cached_df is not None:
                return cached_df

        end = datetime.now().strftime('%Y%m%d')
        start = (datetime.now() - timedelta(days=days + 30)).strftime('%Y%m%d')

        max_retries = 3
        base_delay = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                df = ak.fund_etf_hist_em(
                    symbol=symbol,
                    period='daily',
                    start_date=start,
                    end_date=end,
                    adjust=adjust,
                )
                if df is None or len(df) == 0:
                    return None

                # 统一列名
                df.columns = [c.lower().replace(' ', '_') for c in df.columns]
                df['日期'] = pd.to_datetime(df['日期'])
                df = df.sort_values('日期').reset_index(drop=True)

                # 缓存
                with open(cache_file, 'wb') as f:
                    pickle.dump(df, f)

                return df
            except Exception as e:
                if attempt >= max_retries:
                    print(f"获取 {symbol} 失败: {e}")
                    return None
                delay = base_delay * (2 ** (attempt - 1))
                print(f"获取 {symbol} 第 {attempt}/{max_retries} 次失败: {e}，{delay:.1f}s 后重试")
                time.sleep(delay)

        return None

    def fetch_all(
        self,
        symbols: Dict[str, dict] = None,
        days: int = 120,
    ) -> Dict[str, pd.DataFrame]:
        """
        获取多只ETF数据
        返回: {symbol: df}
        """
        if symbols is None:
            symbols = ALL_SYMBOLS

        result = {}
        symbol_list = list(symbols.keys())
        for index, symbol in enumerate(symbol_list):
            df = self.fetch_history(symbol, days)
            if df is not None and len(df) >= 20:
                result[symbol] = df
            else:
                print(f"⚠️ {symbol} 数据不足，跳过")

            if index < len(symbol_list) - 1:
                self._sleep_between_symbols()

        return result

    def fetch_spot(self, symbol: str) -> Optional[Dict]:
        """获取实时行情（akshare有延迟，仅用于参考）"""
        try:
            df = ak.stock_zh_a_spot_em()
            # ETF在A股代码里搜
            row = df[df['代码'] == symbol]
            if len(row) == 0:
                return None
            return row.iloc[0].to_dict()
        except Exception as e:
            print(f"实时行情获取失败: {e}")
            return None
