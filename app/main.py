from __future__ import annotations

import atexit
import logging
import os
import signal
from pathlib import Path

from flask import Flask, jsonify, render_template

from app.scheduler import Scheduler
from app.services.config_loader import load_config
from app.services.exchange_service import DEFAULT_CACHE
from app.services.log_store import write_json_atomic


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("SUBBARK_DATA_DIR", BASE_DIR / "data"))
CONFIG_PATH = Path(os.environ.get("SUBBARK_CONFIG", DATA_DIR / "subscriptions.toml"))
WEB_PORT = 8080

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
scheduler = Scheduler(CONFIG_PATH, DATA_DIR)


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    notification_log = DATA_DIR / "notification_log.json"
    exchange_rates = DATA_DIR / "exchange_rates.json"
    if not notification_log.exists():
        write_json_atomic(notification_log, {"notifications": []})
    if not exchange_rates.exists():
        write_json_atomic(exchange_rates, DEFAULT_CACHE)


@app.get("/")
def index():
    config = load_config(CONFIG_PATH)
    dashboard = scheduler.get_dashboard()
    return render_template("index.html", title=config.app.title, dashboard=dashboard)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.template_filter("cycle_label")
def cycle_label(value: str) -> str:
    return {"week": "每周", "month": "每月", "quarter": "每季度", "year": "每年"}.get(value, value)


@app.template_filter("status_label")
def status_label(value: str) -> str:
    return {"active": "正常", "expiring": "即将续费"}.get(value, value)


def shutdown(*_args, exit_process: bool = False) -> None:
    scheduler.stop()
    if exit_process:
        raise SystemExit(0)


def main() -> None:
    ensure_data_files()
    config = load_config(CONFIG_PATH)
    logger.info("SubBark starting with %s subscriptions", len(config.subscriptions))
    scheduler.sync_exchange_rates(config)
    scheduler.start()
    atexit.register(shutdown)
    signal.signal(signal.SIGTERM, lambda *_args: shutdown(exit_process=True))
    signal.signal(signal.SIGINT, lambda *_args: shutdown(exit_process=True))
    app.run(host="0.0.0.0", port=WEB_PORT)


if __name__ == "__main__":
    main()
