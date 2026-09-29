"""Self-contained, offline-readable research dashboard for CSI 931743."""

from __future__ import annotations

from html import escape
from urllib.parse import urlsplit


SIGNAL_LABELS = {
    "buy": "买入指令", "add": "加仓", "sell": "卖出指令",
    "rebalance_check": "调仓检查", "hold": "持有", "flat": "空仓 / 清仓复核",
    "cooldown": "冷却期",
}
STATUS_LABELS = {"executed": "已模拟成交", "pending": "待下一交易日验证", "no_fill": "未成交"}
DATA_LABELS = {
    "current": "最新收盘数据已就绪", "awaiting_close": "等待收盘数据",
    "no_current_bar": "当日行情尚不可用", "historical": "历史回看",
}


def _text(value: object) -> str:
    return escape("—" if value is None or value == "" else str(value), quote=True)


def _source_link(value: object) -> str:
    url = str(value or "")
    parsed = urlsplit(url)
    if parsed.scheme == "https" and parsed.netloc:
        return f'<a href="{_text(url)}" rel="noopener noreferrer">{_text(url)}</a>'
    return _text(value)


def _number(value: object, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{float(value):,.{digits}f}{suffix}"


def _cell(value: object, digits: int | None = None, suffix: str = "") -> str:
    return f"<td>{_text(_number(value, digits, suffix) if digits is not None else value)}</td>"


def _label(value: object, mapping: dict[str, str]) -> str:
    return mapping.get(str(value), str(value) if value is not None else "—")


def _badge(value: object, mapping: dict[str, str]) -> str:
    key = str(value)
    return f'<span class="badge badge-{_text(key)}">{_text(_label(value, mapping))}</span>'


def _metric(label: str, value: str, note: str = "") -> str:
    return f'<div class="metric"><span class="metric-label">{_text(label)}</span><strong>{_text(value)}</strong><small>{_text(note)}</small></div>'


def _chart(daily: list[dict], events: list[dict]) -> str:
    points = [(row["date"], float(row["close"]), row.get("ma10")) for row in daily if row.get("close") is not None]
    if not points:
        return '<p class="empty">当前没有可绘制的历史收盘价；未生成模拟行情。</p>'
    prices = [close for _, close, _ in points]
    prices.extend(float(ma) for _, _, ma in points if ma is not None)
    low, high = min(prices), max(prices)
    padding = (high - low) * 0.08 or max(abs(high) * 0.08, 1)
    low -= padding
    high += padding
    width = max(900, min(2400, len(points) * 3 + 110))
    left, right, top, bottom = 78, width - 27, 38, 352
    x = lambda idx: left + (right - left) * idx / max(len(points) - 1, 1)
    y = lambda price: bottom - (float(price) - low) / (high - low) * (bottom - top)
    parts = [f'<svg style="width:{width}px;max-width:none" viewBox="0 0 {width} 415" role="img" aria-labelledby="chart-title chart-description" xmlns="http://www.w3.org/2000/svg">',
             '<title id="chart-title">历史收盘价、十日均线与收盘后信号</title>',
             '<desc id="chart-description">横轴为交易日期，纵轴为指数点位。标记为当日收盘后指令，不代表当日成交。</desc>']
    for step in range(5):
        price = low + (high - low) * step / 4
        pos = y(price)
        parts.append(f'<line class="grid" x1="{left}" y1="{pos:.1f}" x2="{right}" y2="{pos:.1f}"/>')
        parts.append(f'<text class="axis" x="{left - 10}" y="{pos + 4:.1f}" text-anchor="end">{price:,.0f}</text>')
    tick_count = min(7, len(points))
    for i in sorted({round(k * (len(points) - 1) / max(tick_count - 1, 1)) for k in range(tick_count)}):
        parts.append(f'<text class="axis" x="{x(i):.1f}" y="376" text-anchor="middle">{_text(points[i][0])}</text>')
    parts.append('<polyline class="close-line" points="' + ' '.join(f'{x(i):.1f},{y(close):.1f}' for i, (_, close, _) in enumerate(points)) + '"/>')
    # MA10 may be unavailable at the start; never connect across a missing observation.
    segment: list[str] = []
    for i, (_, _, ma) in enumerate(points):
        if ma is not None:
            segment.append(f'{x(i):.1f},{y(ma):.1f}')
        elif segment:
            parts.append('<polyline class="ma-line" points="' + ' '.join(segment) + '"/>')
            segment = []
    if segment:
        parts.append('<polyline class="ma-line" points="' + ' '.join(segment) + '"/>')
    positions = {date: (x(i), y(close)) for i, (date, close, _) in enumerate(points)}
    for event in events:
        kind = event.get("kind")
        location = positions.get(event.get("signal_date"))
        if location is None or kind not in ("buy", "add", "sell", "rebalance_check"):
            continue
        px, py = location
        label = {"buy": "买", "add": "加", "sell": "卖", "rebalance_check": "调"}[kind]
        status = _label(event.get("status"), STATUS_LABELS)
        direction = 1 if kind == "sell" else -1
        marker_y = min(340, max(25, py + direction * 16))
        parts.append(f'<g class="mark mark-{_text(kind)}"><title>{_text(event.get("signal_date"))} 收盘后{_text(_label(kind, SIGNAL_LABELS))} · {_text(status)}；收盘价 {_text(_number(event.get("signal_close")))}</title>'
                     f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{px:.1f}" y2="{marker_y:.1f}"/>'
                     f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.4"/>'
                     f'<text x="{px:.1f}" y="{marker_y:.1f}" dy="{4 if direction == 1 else -2}" text-anchor="middle">{label}</text></g>')
    parts.append('</svg>')
    return '<div class="chart-scroll" tabindex="0" aria-label="可横向滚动的历史价格图">' + ''.join(parts) + '</div>'


def _filters(table_id: str, types: list[tuple[str, str]], statuses: bool = False) -> str:
    options = ''.join(f'<option value="{_text(code)}">{_text(label)}</option>' for code, label in types)
    status_control = ('<label>状态 <select class="filter-status" aria-label="状态筛选"><option value="">全部状态</option>'
                      '<option value="executed">已模拟成交</option><option value="pending">待验证</option><option value="no_fill">未成交</option></select></label>') if statuses else ''
    return (f'<div class="filters" data-table="{table_id}">'
            '<label>起始日期 <input class="filter-from" type="date" aria-label="起始日期"></label>'
            '<label>截止日期 <input class="filter-to" type="date" aria-label="截止日期"></label>'
            f'<label>类型 <select class="filter-type" aria-label="类型筛选"><option value="">全部类型</option>{options}</select></label>'
            f'{status_control}<button type="button" class="filter-reset">清除筛选</button>'
            '<span class="filter-count" role="status" aria-live="polite"></span></div>')


def _events_table(events: list[dict]) -> str:
    rows = []
    for event in reversed(events):
        fields = ("signal_date", "execution_date", "signal_close", "execution_open", "fill_price", "units", "cash_flow", "source_action", "reason")
        cells = (f'<td>{_badge(event.get("kind"), SIGNAL_LABELS)}</td>' + f'<td>{_badge(event.get("status"), STATUS_LABELS)}</td>'
                 + ''.join(_cell(event.get(field), 2 if field in ("signal_close", "execution_open", "fill_price", "units", "cash_flow") else None) for field in fields))
        rows.append(f'<tr data-date="{_text(event.get("signal_date"))}" data-type="{_text(event.get("kind"))}" data-status="{_text(event.get("status"))}">{cells}</tr>')
    return _filters("events-table", [(key, SIGNAL_LABELS[key]) for key in ("buy", "add", "sell", "rebalance_check")], True) + (
        '<div class="table-scroll"><table id="events-table"><caption>收盘后指令及次交易日模拟执行记录（信号日降序）</caption>'
        '<thead><tr><th scope="col">类型</th><th scope="col">状态</th><th scope="col">信号日</th><th scope="col">执行日</th><th scope="col">信号收盘</th><th scope="col">执行开盘</th><th scope="col">模拟成交价</th><th scope="col">指数单位</th><th scope="col">现金变化</th><th scope="col">原始动作</th><th scope="col">原因</th></tr></thead><tbody>'
        + ''.join(rows) + '</tbody></table></div>' + ('<p class="empty">暂无收盘后交易或调仓指令。</p>' if not rows else ''))


def _daily_table(daily: list[dict]) -> str:
    specs = [
        ("date", "信号日期", None), ("signal_kind", "每日状态", None),
        ("open", "开盘", 2), ("high", "最高", 2), ("low", "最低", 2), ("close", "收盘", 2), ("ma10", "MA10", 2),
        ("return_5d_pct", "5日收益 %", 2), ("return_10d_pct", "10日收益 %", 2),
        ("return_20d_pct", "20日收益 %", 2), ("return_60d_pct", "60日收益 %", 2),
        ("raw_momentum", "原始动量", 4), ("adjusted_momentum", "调整后动量", 4),
        ("volatility_penalty", "波动惩罚", 4), ("mean_abs_return_20d_pct", "20日平均绝对收益 %", 2),
        ("trend_ok", "趋势达标", None), ("risk_emergency", "紧急风控", None),
        ("risk_warning", "风险警告", None), ("risk_reasons", "风控原因", None),
        ("raw_action", "原始动作", None), ("effective_action", "有效动作", None),
        ("cooldown_active", "冷却期中", None), ("cooldown_blocked", "冷却期阻止", None),
        ("target_weight", "目标权重 %", "weight"), ("actual_weight", "模拟实际权重 %", "weight"),
        ("cash", "模拟现金", 2), ("index_units", "模拟指数单位", 4), ("portfolio_value", "模拟组合净值", 2),
    ]
    headers = ''.join(f'<th scope="col">{_text(label)}</th>' for _, label, _ in specs)
    rows = []
    for row in reversed(daily):
        cells = []
        for key, _, precision in specs:
            value = row.get(key)
            if key == "signal_kind":
                cells.append(f'<td>{_badge(value, SIGNAL_LABELS)}</td>')
            elif precision == "weight":
                cells.append(_cell(None if value is None else value * 100, 2))
            elif isinstance(value, bool):
                cells.append(_cell("是" if value else "否"))
            else:
                cells.append(_cell(value, precision if isinstance(precision, int) else None))
        rows.append(f'<tr data-date="{_text(row.get("date"))}" data-type="{_text(row.get("signal_kind"))}">{"".join(cells)}</tr>')
    return _filters("daily-table", list(SIGNAL_LABELS.items())) + (
        '<div class="table-scroll"><table id="daily-table"><caption>全部每日状态（最新交易日优先；空仓、重复清仓与冷却期均保留）</caption>'
        f'<thead><tr>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        + ('<p class="empty">暂无每日信号状态。</p>' if not rows else ''))


def _round_trips_table(trips: list[dict]) -> str:
    specs = [("entry_signal_date", "入场信号日", None), ("entry_date", "模拟入场日", None),
             ("entry_open", "入场开盘", 2), ("cost", "成本", 2), ("units", "指数单位", 4),
             ("buy_fills", "买入次数", None), ("exit_signal_date", "离场信号日", None),
             ("exit_date", "模拟离场日", None), ("exit_open", "离场开盘", 2),
             ("proceeds", "所得", 2), ("pnl", "盈亏", 2),
             ("net_return_pct", "净收益 %", 2), ("holding_sessions", "持有交易日", None)]
    header = ''.join(f'<th scope="col">{_text(label)}</th>' for _, label, _ in specs)
    rows = ''.join('<tr>' + ''.join(_cell(trip.get(key), digits) for key, _, digits in specs) + '</tr>' for trip in reversed(trips))
    return (f'<div class="table-scroll"><table id="round-trips-table"><caption>已结束的模拟持仓周期（最新优先）</caption><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table></div>'
            + ('<p class="empty">尚无已结束的模拟持仓周期；未平仓不记为已实现收益。</p>' if not trips else ''))


def render_html(report: dict) -> str:
    """Render the complete research report without network or runtime dependencies."""
    summary = report["summary"]
    daily = report["daily"]
    events = report["events"]
    trips = report["round_trips"]
    params = report["parameters"]
    latest = daily[-1] if daily else None
    latest_kind = latest.get("signal_kind") if latest else summary.get("latest_signal")
    latest_event = next((e for e in reversed(events) if latest and e.get("signal_date") == latest.get("date")), None)
    if latest_event and latest_event.get("execution_date"):
        next_day = (f'下一交易日模拟执行记录：{_text(latest_event["execution_date"])}；'
                    f'{_text(_label(latest_event.get("status"), STATUS_LABELS))}。')
    elif latest_event:
        next_day = (f'执行状态：{_text(_label(latest_event.get("status"), STATUS_LABELS))}；'
                    '下一交易日和模拟成交价格尚未知晓。')
    else:
        next_day = '当日没有新增交易或调仓指令。'
    latest_intro = (f'{_text(latest.get("date"))} 收盘后：{_badge(latest_kind, SIGNAL_LABELS)}。{next_day}'
                    if latest else '暂无信号交易日；没有推断或生成未来指令。')
    weights = params.get("momentum_weights", {})
    weight_description = '、'.join(f'{_text(window)}日 {_text(weight)}' for window, weight in weights.items()) or '未提供'
    source_link = _source_link(report.get("source_url"))
    files = [("summary.json", "完整报告 JSON"), ("daily_signals.csv", "每日信号 CSV"),
             ("trades.csv", "模拟成交 CSV"), ("events.csv", "指令事件 CSV"),
             ("round_trips.csv", "完整持仓周期 CSV"), ("ohlc_history.csv", "原始历史行情 CSV")]
    downloads = ''.join(f'<a href="{filename}" download>{_text(label)}</a>' for filename, label in files)
    metrics = ''.join((
        _metric("回看交易日", str(summary.get("day_count", len(daily))), "每日状态完整保留"),
        _metric("买入 / 加仓 / 卖出", f'{summary.get("buy_count", 0)} / {summary.get("add_count", 0)} / {summary.get("sell_count", 0)}', "已模拟成交次数，不含待执行"),
        _metric("待验证指令", str(summary.get("pending_count", 0)), "尚无模拟成交价格"),
        _metric("模拟组合净值", _number(summary.get("final_value")), "非真实账户"),
        _metric("模拟实际仓位", _number(None if summary.get("position_weight") is None else summary["position_weight"] * 100, 2, "%"), "不等于收盘后新目标"),
        _metric("模拟总收益", _number(summary.get("total_return_pct"), 2, "%"), "含回测假设；非投资建议"),
    ))
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_text(report.get("index_code"))} · {_text(report.get("index_name"))}｜收盘信号研究</title>
<style>
:root{{--ink:#162b38;--muted:#576d79;--line:#dce6e6;--paper:#f4f7f5;--card:#fff;--teal:#087b76;--blue:#255b94;--red:#a24535;--gold:#a86615}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Noto Sans CJK SC","Microsoft YaHei",sans-serif}}a{{color:var(--teal)}}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,.chart-scroll:focus-visible{{outline:3px solid #d79627;outline-offset:2px}}.skip{{position:absolute;top:-5rem;left:1rem;background:white;padding:.5rem}}.skip:focus{{top:1rem;z-index:10}}header{{background:#102e38;color:#ecf4ed;padding:40px max(22px,calc((100vw - 1280px)/2)) 33px}}header .eyebrow{{color:#9bd1bd;letter-spacing:.12em;font-size:.8rem;font-weight:700}}h1{{font-size:clamp(1.8rem,3vw,2.8rem);line-height:1.2;margin:9px 0}}header p{{color:#cfdddb;margin:8px 0}}.meta{{display:flex;flex-wrap:wrap;gap:8px 22px;margin-top:20px;font-size:.92rem}}.meta span{{border-left:2px solid #81b9a6;padding-left:10px}}main{{max-width:1324px;margin:auto;padding:24px 22px 64px}}nav{{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 18px}}nav a,.downloads a{{text-decoration:none;background:white;border:1px solid var(--line);padding:7px 12px;border-radius:7px;font-weight:600}}section{{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:24px;margin:20px 0;box-shadow:0 3px 14px #17373a08}}h2{{font-size:1.35rem;margin:0 0 14px}}h3{{font-size:1.05rem;margin:19px 0 6px}}.subtle,small{{color:var(--muted)}}.lead{{font-size:1.08rem}}.alert{{border-left:4px solid var(--teal);background:#eaf5f1;border-radius:5px;padding:13px 17px;margin:14px 0}}.metrics{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}.metric{{background:#f7faf8;border:1px solid var(--line);border-radius:9px;padding:16px;display:flex;flex-direction:column;gap:4px;min-height:120px}}.metric-label{{color:var(--muted);font-size:.87rem}}.metric strong{{font-size:1.35rem;letter-spacing:-.02em;font-variant-numeric:tabular-nums}}.metric small{{font-size:.78rem}}.badge{{display:inline-block;border-radius:20px;background:#e9f0ee;color:#2d5b59;padding:1px 8px;white-space:nowrap;font-size:.84em;font-weight:700}}.badge-buy,.badge-add,.badge-executed{{background:#d9efe5;color:#16664c}}.badge-sell,.badge-pending{{background:#fff0df;color:#915012}}.badge-rebalance_check,.badge-no_fill{{background:#e9edfa;color:#425885}}.chart-scroll,.table-scroll{{overflow-x:auto;max-width:100%;scrollbar-color:#92aaa7 #ecf2f0}}.chart-scroll svg{{display:block;width:100%;min-width:900px;height:auto;background:#fbfdfb}}svg .grid{{stroke:#e0e8e5;stroke-dasharray:3 4}}svg .axis{{font-size:11px;fill:#61727b}}svg .close-line{{fill:none;stroke:#087b76;stroke-width:2.3;stroke-linejoin:round}}svg .ma-line{{fill:none;stroke:#c08025;stroke-width:1.8;stroke-dasharray:5 3}}svg .mark line{{stroke:currentColor;stroke-width:1.2}}svg .mark circle{{fill:white;stroke:currentColor;stroke-width:2}}svg .mark text{{font-size:10px;fill:currentColor;font-weight:800;paint-order:stroke;stroke:white;stroke-width:2px}}svg .mark-buy,svg .mark-add{{color:#067354}}svg .mark-sell{{color:#aa4238}}svg .mark-rebalance_check{{color:#4c62a1}}.legend{{display:flex;flex-wrap:wrap;gap:8px 20px;font-size:.87rem;color:var(--muted);margin-top:10px}}.legend i{{display:inline-block;width:17px;height:3px;vertical-align:middle;margin-right:5px;background:var(--teal)}}.legend .ma{{background:#c08025}}.filters{{display:flex;align-items:end;gap:8px 14px;flex-wrap:wrap;margin:12px 0}}.filters label{{font-size:.83rem;color:var(--muted);display:grid;gap:3px}}input,select,button{{font:inherit;color:var(--ink);border:1px solid #b9c9c8;border-radius:6px;background:white;padding:6px 8px}}button{{cursor:pointer}}.filter-count{{font-size:.87rem;font-weight:700;color:var(--teal);margin:0 0 7px auto}}table{{border-collapse:collapse;min-width:100%;font-size:.83rem;font-variant-numeric:tabular-nums}}#daily-table{{min-width:2600px}}#events-table{{min-width:1400px}}#round-trips-table{{min-width:1300px}}caption{{text-align:left;color:var(--muted);font-size:.83rem;margin:5px 0}}th,td{{text-align:left;border-bottom:1px solid var(--line);padding:8px 10px;white-space:nowrap}}th{{background:#eaf1ee;color:#284551;position:sticky;top:0}}tbody tr:nth-child(even){{background:#f7faf8}}tbody tr:hover{{background:#eaf5f1}}tr[hidden]{{display:none}}.empty{{color:var(--muted);padding:12px;background:#f7faf8;border-radius:6px}}.downloads{{display:flex;flex-wrap:wrap;gap:9px}}.notes{{padding-left:22px}}.notes li{{margin:8px 0}}footer{{padding:20px;text-align:center;color:var(--muted);font-size:.82rem}}@media(max-width:700px){{header{{padding:29px 18px}}main{{padding:14px 12px 42px}}section{{padding:16px;margin:14px 0}}.metrics{{grid-template-columns:repeat(2,minmax(0,1fr))}}.metric{{padding:11px;min-height:110px}}.metric strong{{font-size:1.05rem}}.filter-count{{width:100%;margin:0}}}}@media(max-width:390px){{.metrics{{grid-template-columns:1fr}}}}
header .subtle{{color:#cfdddb}}
.notes a{{overflow-wrap:anywhere}}
</style></head><body>
<a class="skip" href="#main">跳至报告内容</a>
<header><div class="eyebrow">指数研究 · 每日收盘后信号 · 非实际交易</div><h1>{_text(report.get("index_name"))} <span class="subtle">{_text(report.get("index_code"))}</span></h1><p>仅观察 931743 自身动量，不代表 A 股整体撤退信号；信号不等于成交，指数本身不可直接交易。</p>
<div class="meta"><span>数据状态：{_text(_label(report.get("data_status"), DATA_LABELS))}</span><span>行情请求截止日：{_text(report.get("requested_as_of"))}</span><span>最近可用收盘：{_text(report.get("latest_date"))}</span><span>生成于：<time>{_text(report.get("generated_at"))}</time></span></div></header>
<main id="main"><nav aria-label="报告导航"><a href="#overview">概览</a><a href="#chart">价格与信号</a><a href="#events">指令事件</a><a href="#daily">全部每日状态</a><a href="#trips">持仓周期</a><a href="#method">口径与下载</a></nav>
<section id="overview" aria-labelledby="overview-heading"><h2 id="overview-heading">当前观察</h2><p class="alert">{_text(report.get("status_message"))}数据状态为「{_text(_label(report.get("data_status"), DATA_LABELS))}」，请以最近可用收盘日而非页面生成时间判断新鲜度。</p><p class="lead">{latest_intro}</p><p>最近收盘价：<strong>{_text(_number(latest.get("close") if latest else None))}</strong> 点；MA10：<strong>{_text(_number(latest.get("ma10") if latest else None))}</strong> 点。模拟实际仓位与收盘后的目标指令分开展示；最新模拟仓位 <strong>{_text(_number(None if summary.get("position_weight") is None else summary["position_weight"] * 100, 2, "%"))}</strong>{f'，当日目标仓位 {_text(_number(latest.get("target_weight") * 100 if latest.get("target_weight") is not None else None, 2, "%"))}' if latest else ''}。</p><div class="metrics">{metrics}</div></section>
<section id="chart" aria-labelledby="chart-heading"><h2 id="chart-heading">历史价格与收盘信号</h2><p class="subtle">仅绘制真实保留的每日收盘价与 MA10。标记是信号当日收盘后的指令；鼠标悬停查看日期与状态，键盘或触屏可在下方事件表查阅完整记录，不能视作当日开盘成交。</p>{_chart(daily, events)}<div class="legend"><span><i></i>收盘价</span><span><i class="ma"></i>MA10</span><span>买 / 加 / 卖 / 调：收盘指令（调为调仓检查，未必成交）</span></div></section>
<section id="events" aria-labelledby="events-heading"><h2 id="events-heading">收盘指令与次日模拟执行</h2><p class="subtle">信号日和执行日分列；待验证时执行日、开盘价和成交价均保持未知。未成交不计入实际模拟买卖。</p>{_events_table(events)}</section>
<section id="daily" aria-labelledby="daily-heading"><h2 id="daily-heading">全部历史每日状态</h2><p class="subtle">默认显示全部，按日期倒序；包括持有、空仓、连续清仓复核及冷却期。筛选仅改变可见行，不删减下载文件。</p>{_daily_table(daily)}</section>
<section id="trips" aria-labelledby="trips-heading"><h2 id="trips-heading">已结束的模拟持仓周期</h2>{_round_trips_table(trips)}</section>
<section id="method" aria-labelledby="method-heading"><h2 id="method-heading">研究口径与局限</h2>
<ul class="notes">
<li>固定历史行情起点 {_text(report.get("history_start"))}（供动量预热），分析信号起点 {_text(report.get("signal_start"))}；首个实际信号日期 {_text(report.get("first_signal_date"))}。不以页面生成日虚构缺失行情。</li>
<li>仅研究 {_text(report.get("index_code"))} 的动量与趋势，不进行板块排名或全市场广度判断。目标仓位 {_text(_number(params.get("target_weight") * 100, 2, "%"))}，持有期间允许漂移。历史动作名 reduce_half 表示检查该目标：低于目标可能补仓，高于目标不减仓，未成交时标记「未成交」，并非机械减半。</li>
<li>冷却期 {_text(params.get("cooldown_calendar_days"))} 个自然日；趋势均线 MA{_text(params.get("trend_ma"))}，波动观察窗口 {_text(params.get("volatility_window"))} 日，阈值 {_text(params.get("volatility_threshold_pct"))}%；动量权重：{weight_description}。</li>
<li>模拟初始资金 {_text(_number(params.get("initial_capital")))}；单侧手续费 {_text(params.get("commission_per_side"))}，单侧滑点 {_text(params.get("slippage_per_side"))}。模拟执行使用下一可用交易日开盘假设，不是券商真实成交；存在交易时延、成本、流动性与数据修订风险。</li>
<li>指数不可直接交易；本页不构成投资建议。指数数据来源：{source_link}（外链仅供核查，报告本身离线可用）。</li>
</ul><h3>下载原始研究记录</h3><div class="downloads">{downloads}</div></section>
</main><footer>931743 · 研究用途 · 不代表真实持仓或投资建议</footer>
<script>
// Filters operate only on existing server-rendered rows: no fetch, truncation, or generated observations.
for (const controls of document.querySelectorAll('.filters')) {{
  const table = document.getElementById(controls.dataset.table);
  const rows = Array.from(table.tBodies[0].rows);
  const from = controls.querySelector('.filter-from');
  const to = controls.querySelector('.filter-to');
  const type = controls.querySelector('.filter-type');
  const status = controls.querySelector('.filter-status');
  const count = controls.querySelector('.filter-count');
  function update() {{
    let visible = 0;
    for (const row of rows) {{
      const keep = (!from.value || row.dataset.date >= from.value) &&
        (!to.value || row.dataset.date <= to.value) &&
        (!type.value || row.dataset.type === type.value) &&
        (!status || !status.value || row.dataset.status === status.value);
      row.hidden = !keep;
      if (keep) visible++;
    }}
    count.textContent = `显示 ${{visible}} / ${{rows.length}} 条`;
  }}
  for (const input of controls.querySelectorAll('input, select')) {{ input.addEventListener('input', update); input.addEventListener('change', update); }}
  controls.querySelector('.filter-reset').addEventListener('click', () => {{
    for (const input of controls.querySelectorAll('input, select')) input.value = '';
    update();
  }});
  update();
}}
</script></body></html>'''
