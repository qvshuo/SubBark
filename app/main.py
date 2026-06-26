from __future__ import annotations

import atexit
import logging
import os
import signal
from datetime import date, datetime
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for

from app.scheduler import Scheduler
from app.services.config_loader import load_config
from app.services.exchange_service import DEFAULT_CACHE, ExchangeService
from app.services.log_store import write_json_atomic
from app.services.renewal_state import load_renewal_state, save_renewal_state, set_cycle_renewed
from app.services.subscription_service import build_dashboard, collect_active_cycle_keys


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
    renewal_state = DATA_DIR / "renewal_state.json"
    if not notification_log.exists():
        write_json_atomic(notification_log, {"notifications": []})
    if not exchange_rates.exists():
        write_json_atomic(exchange_rates, DEFAULT_CACHE)
    if not renewal_state.exists():
        write_json_atomic(renewal_state, {"renewed_cycles": {}})


@app.get("/")
def index():
    config = load_config(CONFIG_PATH)
    dashboard = scheduler.get_dashboard()
    return render_template("index.html", title=config.app.title, dashboard=dashboard)


def _is_safe_redirect(target: str) -> bool:
    return target.startswith("/") and not target.startswith("//")


def _today_for_config(config) -> date:
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(config.app.timezone)).date()


def _can_toggle_renewal(config, subscription_id: str, payment_date: str, renewal_date: str) -> bool:
    today = _today_for_config(config)
    exchange = ExchangeService(scheduler.exchange_cache_path, config.app.timezone, config.app.notify_url)
    rates_cache = exchange.load_rates()
    dashboard = build_dashboard(config, rates_cache, exchange.amount_to_cny, today, scheduler.last_check_at, scheduler.renewed_cycles)
    for group in dashboard["category_groups"]:
        for item in group["subscription_items"]:
            if (
                item["subscription_id"] == subscription_id
                and item["payment_date"] == payment_date
                and item["renewal_date"] == renewal_date
            ):
                return item["button_state"]["clickable"]
    return False


@app.post("/renewal-status/toggle")
def toggle_renewal_status():
    subscription_id = request.form.get("subscription_id", "").strip()
    payment_date = request.form.get("payment_date", "").strip()
    renewal_date = request.form.get("renewal_date", "").strip()
    next_url = request.form.get("next", url_for("index"))
    if not _is_safe_redirect(next_url):
        next_url = url_for("index")

    if not subscription_id or not payment_date or not renewal_date:
        return jsonify({"error": "missing parameters"}), 400

    config = load_config(CONFIG_PATH)
    if not _can_toggle_renewal(config, subscription_id, payment_date, renewal_date):
        return jsonify({"error": "subscription not toggleable"}), 400

    state = load_renewal_state(DATA_DIR)
    current_key = f"{subscription_id}:{payment_date}:{renewal_date}"
    current = bool((state.get("renewed_cycles") or {}).get(current_key))
    state = set_cycle_renewed(state, subscription_id, payment_date, renewal_date, not current)
    save_renewal_state(DATA_DIR, state)
    scheduler.refresh_renewal_state()
    return redirect(next_url)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.template_filter("cycle_label")
def cycle_label(value: str) -> str:
    return {"week": "每周", "month": "每月", "quarter": "每季度", "year": "每年"}.get(value, value)


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
