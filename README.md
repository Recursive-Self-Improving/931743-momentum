# 931743 动量信号

跟踪 **中证半导体材料设备主题指数（931743）** 的日线动量、趋势和收盘后信号，生成完整历史 HTML 报告，并通过 GitHub Actions 发布到 GitHub Pages。

项目只观察这个指数，**不再扫描板块 ETF，也不据此判断 A 股是否整体撤退**。没有券商下单、实盘账户或通知服务；报告中的持仓、成交和收益均为假设性研究模拟。

## 本地运行

使用 Python 3.12。[`requirements-report.txt`](requirements-report.txt) 固定 pandas、NumPy 版本，不需要 akshare、行情 Key 或相邻仓库；它不是包含传递依赖及发行包哈希的完整锁文件。

安装了 uv 时：

```bash
# 获取最新完整日线，重放全部历史并生成报告
uv run --no-project --python 3.12 --with-requirements requirements-report.txt python -m src.index_daily --output site

# 历史截止日；不读取此后日线，尚未发生的次日成交保持待执行
uv run --no-project --python 3.12 --with-requirements requirements-report.txt python -m src.index_daily --as-of 2026-09-24 --output site/history
```

已有 Python 环境也可以安装依赖后执行：

```bash
python -m pip install -r requirements-report.txt
python -m src.index_daily --output site
```

直接打开 `site/index.html`。HTML 内嵌样式和筛选脚本，不依赖 CDN 或联网 JavaScript。也可本机预览：

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory site
```

云主机请使用 SSH 端口转发，不要将预览端口暴露到公网。`site/` 和本地研究目录 `reports/` 均忽略提交。

## 每日自动更新与 Pages 部署

工作流：[`.github/workflows/daily-index-report.yml`](.github/workflows/daily-index-report.yml)。

- **定时**：`0 10 * * 1-5`，即周一至周五北京时间 **18:00**。节假日也检查行情。
- **推送**：推送到 `main` 触发；构建只允许在仓库默认分支运行。更改默认分支时，须同步修改 `push.branches`。
- **手动**：Actions → **Daily 931743 momentum signals** → **Run workflow**，选择默认分支；其他分支跳过构建和部署。

首次启用：

1. 在仓库 **Settings → Pages → Build and deployment → Source** 中选择 **GitHub Actions**，并确认仓库允许运行 Actions。
2. 将代码推送到 `main`，或在默认分支手动运行工作流。
3. 部署成功后，从 workflow 的 **github-pages** 环境打开站点，以该环境返回的 URL 为准。

构建安装上述依赖，执行 `python -m src.index_daily --output site`，上传整个 `site/`；部署使用官方 `configure-pages`、`upload-pages-artifact`、`deploy-pages`。使用内置 `GITHUB_TOKEN`：构建仅需 `contents: read`，部署另需 `pages: write` 和 `id-token: write`。无需额外密钥、仓库写权限或 `gh-pages` 分支；仓库套餐、可见性和组织策略须允许 Pages。

行情请求、解析或报告生成失败会使 workflow 失败，**不会把旧报告作为本次成功更新发布**；线上仍可能保留上次成功报告，须核对行情日期与生成时间。GitHub cron 可能延迟，公开仓库长期无活动也可能停用，见 [schedule 文档](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule) 和 [Pages 配置说明](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)。

## 信号与模拟口径

| 项目 | 当前规则 |
|---|---|
| 数据 | 中证官网 931743 OHLC 日线，每次重新获取完整历史，不读本地行情缓存 |
| 历史范围 | 从 `2023-07-19` 预热；信号起点固定为 `2024-09-29`，首个分析交易日为 `2024-09-30` |
| 动量 | 5 / 10 / 20 / 60 日收益率，权重 40% / 30% / 20% / 10% |
| 趋势 | 收盘价严格高于 MA10 |
| 波动惩罚 | 20 日平均绝对日收益超过 5% 时线性降低动量权重，最低降至 0 |
| 清仓 | 调整后动量不大于 0，或收盘价未高于 MA10 |
| 预警 | 最近 5 次调整后动量严格递减，即 4 次相邻下降；清仓优先 |
| 仓位 | 建仓目标为 1/3；正常持有时允许漂移，不每日再平衡，也不是硬性上限 |
| 冷却 | 清仓执行后 3 个自然日；空仓时重复清仓指令也重置日期 |
| 执行 | 当日收盘决定，下一实际返回交易日开盘模拟执行 |
| 资金与费用 | 初始资金 10 万，单边佣金 0.03%、滑点 0.1%，现金不计息 |

动量评分保留两位小数后参与风控。预警沿用历史动作名 `reduce_half`，但其实际含义是**检查 1/3 目标仓位**：可能补买或不成交，不会机械减半。此次代码清理保留这些历史行为，不借清理改变仓位或择时规则。算法、执行公式和状态说明见 [`docs/DESIGN.md`](docs/DESIGN.md)。

每次运行都从固定起点重放风险、冷却和模拟账户，不依赖上一次 runner 的状态，也不滚动裁剪历史。同一行情输入不会追加重复记录；数据源修订旧行情时，重算结果可能变化。

使用 `Asia/Shanghai`，15:30 前排除当天 K 线；历史截止日不可晚于北京时间今天。报告明确区分：

- `current`：已取得请求当日的完整日线。
- `awaiting_close`：工作日 15:30 前，只有此前完整日线，不是今日收盘判断。
- `no_current_bar`：未取得请求当日完整日线，可能休市或源数据尚未发布，不能解释为“今日无信号”。
- `historical`：历史截止日回看。

## 页面与下载

页面展示收盘价／MA10、收盘指令、全部每日状态、已结束的持仓周期，并支持日期／类型／状态筛选。信号日与模拟执行日分列；最新买卖指令保持待执行，不预先填写未来日期或价格。空仓期间重复清仓和冷却拦截不计作新的卖出成交。

| 输出 | 内容 |
|---|---|
| `site/index.html` | 完整历史信号页面 |
| `site/summary.json` | 数据状态、参数、汇总及全部报告记录 |
| `site/daily_signals.csv` | 全部逐日状态、评分、冷却、持仓和费用后权益 |
| `site/events.csv` | 收盘指令，含待执行、已模拟成交及未成交检查 |
| `site/trades.csv` | 实际产生的假设性模拟买卖明细 |
| `site/round_trips.csv` | 已结束持仓周期的成本、收益与持有交易日数 |
| `site/ohlc_history.csv` | 包含预热期的完整行情 |

指数本身不可直接交易。模拟使用分数指数单位，不包含实际 ETF 的跟踪误差、整数份额、涨跌停、停牌和委托成交约束；不代表可直接执行的 ETF 收益。期末未平仓市值计入组合权益，但不计入已结束持仓周期。

## 代码与验证

运行链路为 `index_daily` → `index_data` / `index_analysis` / `index_report`；分析使用 `IndexStrategy`、`MomentumEngine` 和 `RiskController`，参数集中在 [`src/config.py`](src/config.py)。旧多 ETF 入口、缓存、回测引擎、通知模块和对应依赖已移除，唯一运行入口是 `python -m src.index_daily`。

运行测试：

```bash
uv run --no-project --python 3.12 --with-requirements requirements-report.txt --with pytest python -m pytest -q
```

测试覆盖行情解析边界、收盘截止、次日开盘与跳空记账、冷却、单指数风控和失败不替换旧报告。联网取数与实际页面仍需通过上面的报告命令验证；本地通过不等于已经在 GitHub 部署。

## 风险提示

仅供研究与学习，不构成投资建议。历史模拟表现不代表未来收益。
