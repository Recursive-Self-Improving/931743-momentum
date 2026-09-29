"""Fetch and validate official CSI daily index candles without caching."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

INDEX_CODE = "931743"
INDEX_NAME = "中证半导体材料设备主题指数"
SOURCE_URL = "https://www.csindex.com.cn/csindex-home/perf/index-perf"
# First verified complete OHLC session; earlier/non-trading starts may create a synthetic point.
HISTORY_START = date(2023, 7, 19)


@dataclass(frozen=True, slots=True)
class Candle:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float


class DataError(ValueError):
    """Missing or invalid CSI market data."""


def parse_candles(payload: dict, start: date, end: date) -> list[Candle]:
    """Validate the requested index and start coverage before returning sorted candles."""
    if not isinstance(payload, dict) or str(payload.get("code")) != "200":
        raise DataError("中证接口未返回成功状态。")
    raw_rows = payload.get("data")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise DataError("中证接口没有返回日线；拒绝生成不完整报告。")

    candles: list[Candle] = []
    seen: set[date] = set()
    try:
        for row in raw_rows:
            if str(row["indexCode"]) != INDEX_CODE:
                raise DataError("行情指数代码不匹配。")
            day = datetime.strptime(row["tradeDate"], "%Y%m%d").date()
            if day in seen or day.weekday() >= 5 or not start <= day <= end:
                raise DataError(f"行情日期重复、非工作日或越界：{day}")
            seen.add(day)
            opening, high, low, close, volume, amount_yi = (
                float(row[key]) for key in ("open", "high", "low", "close", "tradingVol", "tradingValue")
            )
            if not all(math.isfinite(value) for value in (opening, high, low, close, volume, amount_yi)):
                raise DataError(f"行情含非有限数值：{day}")
            if not (0 < low <= min(opening, close) <= max(opening, close) <= high):
                raise DataError(f"OHLC 高低价关系异常：{day}")
            if volume < 0 or amount_yi < 0:
                raise DataError(f"成交量或成交额为负：{day}")
            amount = amount_yi * 100_000_000
            if not math.isfinite(amount):
                raise DataError(f"成交额超出可表示范围：{day}")
            candles.append(Candle(day, opening, high, low, close, volume, amount))
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        if isinstance(error, DataError):
            raise
        raise DataError(f"无法解析中证日线字段：{error}") from error

    candles.sort(key=lambda candle: candle.date)
    if candles[0].date != start:
        raise DataError(f"行情未覆盖请求起点 {start}，可能被接口截断；拒绝生成不完整报告。")
    return candles


def fetch_candles(start: date, end: date) -> list[Candle]:
    """Fetch fresh official CSI OHLC for the inclusive date interval."""
    query = urlencode({
        "indexCode": INDEX_CODE,
        "startDate": start.strftime("%Y%m%d"),
        "endDate": end.strftime("%Y%m%d"),
    })
    request = Request(
        f"{SOURCE_URL}?{query}",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.csindex.com.cn/",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (URLError, OSError, ValueError) as error:
        raise DataError(f"获取中证日线失败：{error}") from error
    return parse_candles(payload, start, end)
