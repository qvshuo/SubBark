# AGENTS.md

## 项目约定

- Python 版本：3.12+（`tomllib`、`zoneinfo`、PEP 604 联合类型均为内置）。
- Web 框架：Flask，默认监听 `0.0.0.0:8080`，路由：`/`（仪表盘）、`/health`、POST `/renewal-status/toggle`。
- HTTP 客户端：httpx（Frankfurter 汇率与 Bark 推送）。
- 日期计算：python-dateutil（`dateutil.relativedelta`）。
- 配置格式：TOML，通过 Python 标准库 `tomllib` 读取。
- **不使用数据库，不使用 cron**；后台任务由 `app/scheduler.py` 里的 `threading.Thread` 守护线程轮询实现。
- 无单元测试、无 CI 流程、无 pyproject.toml，依赖通过 `requirements.txt` 安装。

## 目录说明

- `app/main.py`：Flask 入口、路由、信号注册、`Scheduler` 启动。
- `app/scheduler.py`：后台轮询、汇率同步、通知去重、定期检查。
- `app/services/config_loader.py`：TOML 配置读取与校验（`BILLING_CYCLES = {week, month, quarter, year}`）。
- `app/services/exchange_service.py`：Frankfurter 汇率同步、人民币换算、Bark HTTP 调用。
- `app/services/log_store.py`：JSON 文件原子读写（`NamedTemporaryFile` + `os.replace`）和通知日志截断（默认 1000 条）。
- `app/services/subscription_service.py`：订阅状态、续费日期计算、费用汇总、分类分组。
- `app/templates/index.html` 和 `app/static/style.css`：仪表盘页面，包含 `/renewal-status/toggle` 状态切换按钮。

## 数据文件

- `data/subscriptions.toml`：本地订阅配置，包含 Bark URL，不应提交。
- `data/notification_log.json`：运行时通知去重日志，不应提交。
- `data/exchange_rates.json`：运行时汇率缓存，不应提交。
- `data/renewal_state.json`：用户手动“已续费”状态，不应提交。
- `subscriptions.example.toml`：可提交的示例配置。
- 首次运行前需手动 `mkdir -p data` 并从 `subscriptions.example.toml` 复制配置；`data/` 已被 `.gitignore` 忽略。

## 环境变量

- `SUBBARK_DATA_DIR`：数据目录，默认 `<repo>/data`。
- `SUBBARK_CONFIG`：配置文件路径，默认 `$SUBBARK_DATA_DIR/subscriptions.toml`。
- `LOG_LEVEL`：日志级别，默认 `INFO`。

## 开发命令

- 创建环境：`uv venv .subbark`（`.subbark/` 已在 `.gitignore`）。
- 安装依赖：`uv pip install -r requirements.txt`。
- 本地运行：`uv run python -m app.main`。
- 语法检查：`uv run python -m compileall app`（仓库内唯一的静态检查手段）。
- Docker 运行：`docker compose up -d --build`（基于 `docker-compose.example.yml` 复制为 `docker-compose.yml`）。
- 修改订阅后无需重建镜像，Docker 部署执行 `docker compose restart subbark` 即可。

## 行为规则

- `payment_date` 是续费锚点日期，程序通过 `next_renewal_date` 自动滚动到不早于今日的下一次续费日。
- `subscription_id` 由 `name + payment_date + billing_cycle + amount + currency`（`amount` 保留 8 位小数）通过 SHA256 取前 16 位生成，**不包含 `category`**。
- 订阅状态只包含 `active` 和 `expiring`，不维护过期状态；`expiring` 触发条件为 `today >= renewal_date - remind_before_days`。
- `quarter` 计费周期在 `subscription_service.add_cycles` 中特判为 `months * 3`，不要改写为 `quarters`。
- 汇率以 CNY 为基准缓存，调用 `https://api.frankfurter.dev/v1/latest`（`from=CNY`）；非 CNY 金额按 `amount / rate` 换算人民币。连续同步失败 7 次后会通过 Bark 推送“汇率同步异常”告警，每天最多一次。
- 货币在配置加载阶段会被统一转为大写。
- `notify_enabled` 是每个 `[[subscriptions]]` 的可选布尔字段，缺省为 `true`；设为 `false` 时该订阅进入 `expiring` 也不会发送 Bark。
- Bark 去重维度为 `subscription_id + payment_date + renewal_date`，通知日志超过 1000 条时按尾部截断。
