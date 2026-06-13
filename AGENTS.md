# AGENTS.md

## 项目约定

- Python 版本：3.12+
- Web 框架：Flask
- HTTP 客户端：httpx
- 日期计算：python-dateutil
- 配置格式：TOML，通过 Python 标准库 `tomllib` 读取
- 不使用数据库，不使用 cron，后台任务由 Python 线程轮询实现。

## 目录说明

- `app/main.py`：Flask 入口、路由、启动初始化。
- `app/scheduler.py`：后台轮询、通知去重、定期检查。
- `app/services/config_loader.py`：TOML 配置读取与校验。
- `app/services/exchange_service.py`：Frankfurter 汇率同步、人民币换算、Bark HTTP 调用。
- `app/services/log_store.py`：JSON 文件读写和通知日志截断。
- `app/services/subscription_service.py`：订阅状态、续费日期计算、费用汇总、分类分组。
- `app/templates/index.html` 和 `app/static/style.css`：只读前端页面。

## 数据文件

- `data/subscriptions.toml`：本地订阅配置，包含 Bark URL，不应提交。
- `data/notification_log.json`：运行时通知去重日志，不应提交。
- `data/exchange_rates.json`：运行时汇率缓存，不应提交。
- `subscriptions.example.toml`：可提交的示例配置。

## 开发命令

- 创建环境：`uv venv .subbark`
- 安装依赖：`uv pip install -r requirements.txt`
- 本地运行：`uv run python -m app.main`
- 语法检查：`uv run python -m compileall app`
- Docker 运行：`docker compose up -d --build`

## 行为规则

- `payment_date` 是续费锚点日期，程序会自动滚动计算下一次续费日。
- `subscription_id` 基于 `name + payment_date + billing_cycle + amount + currency` 生成，不包含 `category`。
- 状态只包含 `active` 和 `expiring`，不维护过期状态。
- 汇率以 CNY 为基准缓存；非 CNY 金额通过 Frankfurter 汇率换算人民币。
- Bark 去重维度为 `subscription_id + payment_date + renewal_date`。
