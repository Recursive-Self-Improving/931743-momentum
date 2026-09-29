# Project Instructions

## Lessons

- 当前唯一运行入口是 `python -m src.index_daily`，以 `.github/workflows/daily-index-report.yml` 的调用链为清理边界。旧 `main.py`、`run.sh`、多 ETF 数据缓存／回测／runner／通知模块及 `requirements.txt` 已删除，不再维护旧 paper/live 入口；部署状态仍须与源码说明分别核查。
- `../931743-oversold/` 对应的指数是 `931743`（中证半导体材料设备主题指数）；其官网取数方式已独立移植到 `src/index_data.py`，不依赖相邻仓库或 akshare。完整历史从真实交易日 `2023-07-19` 起请求，避免官网接口在非交易日起点插入图表补点；北京时间 15:30 前应排除当天未完成日线。
- `IndexStrategy` 仅接收一个指数的历史和实际是否持仓，不再使用 `RotationStrategy`、`universe` 或 ETF 池。单指数的旧广度风控等价于“调整后动量不大于 0 或未通过 MA10 即清仓”；最近 5 次两位小数评分严格递减才预警，相等会打断。
- `TARGET_WEIGHT=1/3` 替代多标的 `MAX_HOLDINGS`；报告参数使用 `target_weight` 和 `momentum_decline_observations`。历史动作值 `reduce_half` 仍表示 1/3 目标检查，可能补买或不成交，不是减半。保持次日开盘、费用后权益、自然日冷却、空仓清仓也重置日期及正常持仓漂移，不能借清理改变这些历史口径。
- 单指数分析已在 Python 3.12.3、pandas 3.0.6、NumPy 2.5.3 上实跑。当前系统 Python 无 pip；可用 `uv pip install --target <临时目录> pandas numpy` 隔离补足策略依赖，无须修改全局环境或安装 ETF 数据接口依赖。
- 分析反向交易时，应冻结原策略的信号时点并独立记账，不能把反向持仓反馈给原策略重新生成另一套信号；`daily_signals.csv` 中空仓期间持续的 `clear_all` 不等于每天新增卖出。必须区分初始全现金与已有仓位，并计入期末未平仓浮盈亏；反向多头/现金切换不等于做空，也不等于将原收益取负。
- `python -m src.index_daily` 每次联网取全量行情，重放固定 `2024-09-29` 起点以来的全部状态；不能把历史起点每天向前滚动，否则持仓和冷却状态会改变。依赖由 `requirements-report.txt` 固定，可用 `uv run --no-project --python 3.12 --with-requirements requirements-report.txt python -m src.index_daily`，不依赖系统 pip。
- 报告中的 `events.csv` 包含待执行和未成交调仓检查，`trades.csv` 仅记录实际产生的假设性模拟成交；两者条数可能不同。最新日线的指令不可提前写入未来开盘成交。Pages 工作流周一至周五北京时间 18:00 检查，休市或缺少今日 K 线须明确标注，不能当作今日没有信号。
- ARM64 主机的默认浏览器自动安装可能失败；本次使用 Playwright 下载的 ARM Chromium，配合临时解包的运行库、CJK 字体及本地 CDP 完成桌面／手机烟测，没有修改系统软件包。浏览器原生日期输入的通用 `fill` 曾将 `2026-01-01` 填成 `60101-02-02`；验证筛选时应核对实际 input.value，而不是误判业务筛选失效。
- 使用 CDP 附着浏览器时，`open` 的 viewport 参数未必改变实际页面尺寸；烟测应核对 `window.innerWidth`，必要时通过 `page.setViewport` 显式设置后再截图，不能只信工具返回的视口元数据。
- `reports/` 是本地分析产物，`site/` 是 Pages 构建产物；两者分别由根级 `/reports/`、`/site/` 规则忽略，不应提交生成的 CSV、JSON 或 HTML。新增忽略规则前应检查是否已有文件被跟踪，忽略规则本身不会取消已有跟踪。
- 文档与页面聚焦 931743 自身的动量研究，不把它描述为全市场撤退判断或可执行的 ETF 策略；不恢复旧板块池、无依据业绩或未实现的券商／通知能力。
- `src/index_report.py` 仅依赖标准库；审计生成页面时可用 `site/summary.json` 重放 `render_html`，与忽略的 `site/index.html` 逐字节比对，再检查浏览器脚本、资源请求及文本／属性／SVG 转义，不能只审计生成器或只信任页面说明。
- `requirements-report.txt` 只固定 pandas、NumPy 两个直接依赖，不是含传递依赖和发行包哈希的完整锁文件；GitHub Actions 的 `@vN` 也是可移动标签，不能据这些版本标记断言构建供应链已验证。
- 删除旧路径时同时移除其默认池、无调用方法、中文 ETF 行情列适配、依赖和测试；本次对同一份 776 根官方行情及历史截止日／构造行情共 14 组重放比对，除风控说明文本外所有逐日字段、动作、时点、成交和权益均一致。此类清理应用固定输入比对，不能把数据源修订误判为代码回归。
