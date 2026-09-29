# Project Instructions

## Lessons

- `run.sh` 硬编码 `/root/.hermes/hermes-agent/venv/bin/python3`，不能把它当作可移植的环境初始化脚本；核查运行状态时应分别检查启动脚本和当前 Python 的依赖。
- `main.py` 的 `daily --mode paper` 和 `daily --mode live` 共用目标权重 JSON 更新逻辑。该分支不提交券商订单，也不维护成交、份额或每日盈亏账本，不能据模式名称认定模拟盘或实盘已经完整实现。
- 数据缓存、持仓状态及信号日志默认写入 `~/a股动量轮动策略/`，而不是仓库目录。仓库代码、用户定时任务和运行产物需分别核查；README 的部署描述不等于当前主机已部署。
- `../931743-oversold/` 对应的指数是 `931743`（中证半导体材料设备主题指数）；其官网取数方式已独立移植到 `src/index_data.py`，不依赖相邻仓库或 akshare。完整历史从真实交易日 `2023-07-19` 起请求，避免官网接口在非交易日起点插入图表补点；北京时间 15:30 前应排除当天未完成日线。
- `RotationStrategy` 和 `RiskController` 支持实例级 `universe` 参数，默认仍为原 `ETF_POOL`；单指数入口显式传入 931743，禁止通过修改全局池适配。旧 `BacktestEngine.run` 在快照少于 3 个标的时仍跳过全部交易日。单指数研究不等于原多 ETF 轮动业绩；保留 `MAX_HOLDINGS=3` 时单次目标仍为 1/3 仓位。
- 当前回测引擎使用同日收盘信号与成交价、交易前权益记录和线性年化，不能直接当作无前视偏差的复合收益结果。指数分析应明确次日开盘执行、费用后权益和 CAGR；原冷却规则按自然日计，空仓时执行 `clear_all` 也重置日期，持有仓位也不会自动再平衡至 1/3。
- 单指数分析已在 Python 3.12.3、pandas 3.0.6、NumPy 2.5.3 上实跑。当前系统 Python 无 pip；可用 `uv pip install --target <临时目录> pandas numpy` 隔离补足策略依赖，无须修改全局环境或安装 ETF 数据接口依赖。
- 分析反向交易时，应冻结原策略的信号时点并独立记账，不能把反向持仓反馈给原策略重新生成另一套信号；`daily_signals.csv` 中空仓期间持续的 `clear_all` 不等于每天新增卖出。必须区分初始全现金与已有仓位，并计入期末未平仓浮盈亏；反向多头/现金切换不等于做空，也不等于将原收益取负。
- `python -m src.index_daily` 每次联网取全量行情，重放固定 `2024-09-29` 起点以来的全部状态；不能把历史起点每天向前滚动，否则持仓和冷却状态会改变。依赖由 `requirements-report.txt` 固定，可用 `uv run --no-project --python 3.12 --with-requirements requirements-report.txt python -m src.index_daily`，不依赖系统 pip。
- 报告中的 `events.csv` 包含待执行和未成交调仓检查，`trades.csv` 仅记录实际产生的假设性模拟成交；两者条数可能不同。最新日线的指令不可提前写入未来开盘成交。Pages 工作流周一至周五北京时间 18:00 检查，休市或缺少今日 K 线须明确标注，不能当作今日没有信号。
- ARM64 主机的默认浏览器自动安装可能失败；本次使用 Playwright 下载的 ARM Chromium，配合临时解包的运行库、CJK 字体及本地 CDP 完成桌面／手机烟测，没有修改系统软件包。浏览器原生日期输入的通用 `fill` 曾将 `2026-01-01` 填成 `60101-02-02`；验证筛选时应核对实际 input.value，而不是误判业务筛选失效。
- `reports/` 是本地分析产物，`site/` 是 Pages 构建产物；两者分别由根级 `/reports/`、`/site/` 规则忽略，不应提交生成的 CSV、JSON 或 HTML。新增忽略规则前应检查是否已有文件被跟踪，忽略规则本身不会取消已有跟踪。
- 项目文档聚焦A股ETF策略自身的逻辑与交易约束，采用中性表述；整理文案时保留既有的货币基金等资产类别名称，不改变交易规则。
- `src/index_report.py` 仅依赖标准库；审计生成页面时可用 `site/summary.json` 重放 `render_html`，与忽略的 `site/index.html` 逐字节比对，再检查浏览器脚本、资源请求及文本／属性／SVG 转义，不能只审计生成器或只信任页面说明。
- `requirements-report.txt` 只固定 pandas、NumPy 两个直接依赖，不是含传递依赖和发行包哈希的完整锁文件；GitHub Actions 的 `@vN` 也是可移动标签，不能据这些版本标记断言构建供应链已验证。
- Python 3.12 的 `SMTP.starttls()` 默认上下文不验证证书或主机名；本项目通知路径已用本地自签证书与假凭据复现，认证前应显式传入 `ssl.create_default_context()`。ETF 缓存的 `pickle.load` 同样是执行边界，后置的 DataFrame／日期检查不能保护被篡改的缓存；这两项不属于独立 HTML 页面的执行路径。
