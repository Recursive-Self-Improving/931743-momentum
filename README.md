# A股ETF动量轮动策略

> Momentum Rotation 的A股ETF适配版。
> 核心思想: 右侧起步追强者，卖弱者，强变弱也要卖，看整体不看单票。强者变少、弱者大面积增加时清仓避险。

## 931743 每日信号与 GitHub Pages

新增独立入口，对 **中证半导体材料设备主题指数（931743）** 更新本项目的动量信号，并生成可离线打开的 HTML。这里只采用参考项目的中证官网取数方式，不使用 RSI／布林带超卖规则，运行时也不依赖相邻仓库。

### 自动更新与首次部署

工作流：[`.github/workflows/daily-index-report.yml`](.github/workflows/daily-index-report.yml)。

- **定时**：`0 10 * * 1-5`，即周一至周五北京时间 **18:00**。节假日也检查；没有新日线时标注“可能休市或源数据未发布”，不虚构信号，也不将旧数据称为今日判断。
- **推送**：推送到 `master` 后生成并部署；如果更改默认分支，也需更新 workflow 的 `push.branches`。
- **手动**：Actions → **Daily 931743 momentum signals** → **Run workflow**。只有默认分支允许部署，其他分支的手动执行跳过。

首次启用：

1. 在仓库 **Settings → Pages → Build and deployment → Source** 中选择 **GitHub Actions**，并确认仓库允许运行 Actions。
2. 将这些代码与 workflow 提交、推送到默认分支；若此前已推送，则手动运行一次上述 workflow。
3. 部署成功后，从 workflow 的 **github-pages** 环境打开站点；以该环境实际给出的 URL 为准。

使用官方 `configure-pages`、`upload-pages-artifact`、`deploy-pages`，上传 `site/` 中的 HTML 与 CSV/JSON。工作流使用内置 `GITHUB_TOKEN`，构建仅需 `contents: read`，部署阶段另需 `pages: write` 和 `id-token: write`；无需额外行情 Key、仓库写权限或 `gh-pages` 分支。仓库套餐、可见性和组织策略须允许 Pages。

行情请求或报告生成失败会使 workflow 失败，**不发布旧数据作为本次成功更新**；线上保留上一份成功报告，应查看行情日期与生成时间。GitHub cron 可能延迟，并非准点服务；公开仓库长期无活动也可能被停用，参见 [GitHub schedule 文档](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。Pages 配置参见 [GitHub 官方说明](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)。

### 本地运行

Python 3.12，依赖锁定在 [`requirements-report.txt`](requirements-report.txt)，无需安装 akshare。安装了 uv 时可直接运行：

```bash
uv run --no-project --python 3.12 --with-requirements requirements-report.txt python -m src.index_daily --output site

# 历史截止日；不读取此后日线，未发生的次日成交保持待执行
uv run --no-project --python 3.12 --with-requirements requirements-report.txt python -m src.index_daily --as-of 2026-09-24 --output site/history
```

已有 Python 环境也可以先 `python -m pip install -r requirements-report.txt`，再执行 `python -m src.index_daily --output site`。

打开 `site/index.html` 即可；HTML 不依赖 CDN 或联网 JavaScript。也可本机预览：

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory site
```

云主机请用 SSH 端口转发，不要将开发预览端口直接暴露到公网。`site/` 为忽略提交的生成目录，Actions 每次从源码重新生成。

### 页面与历史口径

- **完整历史持续保留**：信号起点固定为上次分析的 `2024-09-29`，首个交易日为 `2024-09-30`；之后只延长，不每天滚动裁剪两年窗口。指标从 `2023-07-19` 的真实行情预热。
- 每次重新取全量官方日线并重放风险、冷却和模拟持仓，不依赖上次 Actions runner 的状态或缓存。同一行情输入重复运行不会追加重复记录；数据源修订旧行情时，重算结果也可能改变。
- 使用 `Asia/Shanghai`；15:30 前排除今日 K 线。历史截止日不可晚于北京时间今天。页面区分 `current`、`awaiting_close`、`no_current_bar` 和 `historical`。
- 页面包含收盘价／MA10 与信号标记、全部指令事件、全部逐日状态、已结束持仓周期；日期／类型／状态可筛选，默认保留全部记录。空仓期间重复 `clear_all` 与冷却期拦截不会被计作新的卖出成交。
- 收盘信号与**下一实际返回交易日开盘**的模拟执行分列；最新买卖指令先标为待执行，不预先填写未来交易日期和价格。`reduce_half` 是原代码的单个 1/3 目标检查，可能补买或不成交，不冒称真实减半。
- 复用 `MomentumEngine`、`RiskController`、`RotationStrategy`；通过实例级候选池选择 931743，不修改全局 ETF 池。保留原权重、MA10、波动惩罚、每标的 1/3 目标及 3 个自然日冷却；空仓清仓指令也重置冷却日期。仓位会漂移，不是硬性 1/3 上限。
- 这是单指数、分数单位的研究模拟，不是原多 ETF 组合业绩，也不下单。初始资金 10 万，单边佣金 0.03%、滑点 0.1%，现金不计息；不包含实际 ETF 的跟踪误差、整数份额及成交约束。

| 输出 | 内容 |
|---|---|
| `site/index.html` | 完整历史信号页面 |
| `site/summary.json` | 数据状态、参数、汇总及全部报告记录 |
| `site/daily_signals.csv` | 所有逐日状态，含重复清仓、冷却及持仓 |
| `site/events.csv` | 收盘指令与待执行／已模拟成交／未成交状态 |
| `site/trades.csv` | 实际产生的假设性模拟买卖明细 |
| `site/round_trips.csv` | 已结束的持仓周期与扣费收益 |
| `site/ohlc_history.csv` | 完整预热及分析 OHLC 历史 |

已实跑截至 `2026-09-28` 的官方行情：776 根日线、484 日分析状态、23 次建仓、3 次补买、23 次卖出；日期、价格、费用和资金流与此前分析一致。两次实时取数生成的历史 CSV 完全一致；回溯至 `2026-09-24` 时卖出保持待执行，没有提前生成 `09-28` 的成交。32 项测试通过，覆盖解析边界、收盘截止、次日开盘时序、冷却和失败不替换旧报告。

桌面及 390px 手机视口已用真实 Chromium 打开验证：484 行逐日状态、50 条指令事件（49 笔成交及 1 条未成交调仓检查）、日期／类型／状态筛选、全部下载链接及待执行卖出均正确显示，页面无横向溢出或 JavaScript 异常。workflow 通过 actionlint 检查；这不等于已在 GitHub 服务上部署，首次发布仍需上述仓库设置与推送步骤。

## 回测表现

| 指标 | 数值 |
|------|------|
| 总收益率 | +17.90% (近6个月) |
| 年化收益 | +38.55% |
| 最大回撤 | -8.18% |
| 夏普比 | 2.12 |
| 超额 vs 沪深300 | +9.47% |
| 交易次数 | 74次 (半年) |

## 快速开始

```bash
# 通用启动（自动检查依赖、使用正确的 Python 环境）
./run.sh backtest --days 180      # 运行回测
./run.sh daily --mode signal      # 每日信号
./run.sh daily --mode paper       # 模拟盘

# 如果确信你的环境已正确安装 akshare，也可以直接用 python3
python3 main.py backtest --days 180
python3 main.py daily --mode signal
```

## 策略架构

```
数据层: akshare → ETF历史日线
    ↓
引擎层: 动量计算 + 趋势确认 + 波动率惩罚
    ↓
策略层: 按动量排序 → 取Top N → 等权分配
    ↓
风控层: 强弱分化监测 → 清仓/降仓/持仓
    ↓
执行层: 模拟/实盘 → 通知
```

## 核心参数

| 参数 | 设置 | 说明 |
|------|------|------|
| 动量窗口 | 5/10/20/60日 | 加权40%/30%/20%/10% |
| 趋势确认 | 10日均线 | 收盘价在均线之上才考虑 |
| 最大持仓 | 3只 | 等权分配 |
| 风控强标阈值 | 20% | <20%标的动量>0 → 清仓 |
| 清仓冷却期 | 3天 | 避免频繁进出 |
| 每日波动率上限 | 5% | 超过降动量权重 |

## ETF池

| 类别 | 标的 | 名称 |
|------|------|------|
| 大盘价值 | 510300 | 沪深300ETF |
| 中盘成长 | 510500 | 中证500ETF |
| 科技创新 | 588000 | 科创50ETF |
| 创业成长 | 159915 | 创业板ETF |
| 小盘 | 512100 | 中证1000ETF |
| 科技 | 512480 | 半导体ETF |
| 新能源 | 515030 | 新能源ETF |
| 金融 | 512800 | 银行ETF |
| 医药 | 512010 | 医药ETF |
| AI/通信 | 515880 | 通信ETF |
| 芯片 | 159995 | 芯片ETF |
| 基建 | 516970 | 基建ETF |
| 避险 | 511880 | 银华日利货币基金 |
| 避险 | 511010 | 国债ETF |

## 实盘对接

### 方案1: QMT量化平台 (推荐)
QMT支持Python API，可以直接调用本策略。

```python
# 在QMT中的模板脚本
from xtquant import xtdata, xttrade
from a股轮动策略.src.daily_runner import DailyRunner

runner = DailyRunner()
decision = runner.run()

# 执行交易
for sym, weight in decision['target_holdings'].items():
    # QMT下单逻辑
    pass
```

### 方案2: 同花顺EasyTrade
- 使用本策略生成信号文件
- 同花顺开启条件单，仿佋手动确认执行

### 方案3: 邮件/微信通知+手动下单
- 配置SMTP或微信机器人webhook
- 每日收到信号后手动执行

### 方案4: 模拟盘
- `python main.py daily --mode paper`
- 系统会跟踪假设持仓，记录每日收益，不真实下单
- 验证一段时间后再实盘

## 环境变量

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your_email@gmail.com"
export SMTP_PASS="your_password"
export TO_EMAIL="target@email.com"
export WECHAT_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
```

## 定时任务

931743 的 GitHub Actions 调度与 Pages 启用步骤见上文。原 ETF `main.py daily` 如需本机定时运行，仍需自行配置；仓库说明不代表当前主机已安装 cron。

## 声明

**风险警示**: 本策略仅供研究和学习，不构成投资建议。任何回测表现均不代表未来收益。实盘前请充分测试。
