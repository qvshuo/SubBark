from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.log_store import read_json, write_json_atomic


RENEWAL_STATE_KEY = "renewed_cycles"
MIN_BUTTON_WINDOW_DAYS = 7


def _state_path(data_dir: Path) -> Path:
    return data_dir / "renewal_state.json"


def load_renewal_state(data_dir: Path) -> dict[str, Any]:
    return read_json(_state_path(data_dir), {RENEWAL_STATE_KEY: {}})


def save_renewal_state(data_dir: Path, state: dict[str, Any]) -> None:
    write_json_atomic(_state_path(data_dir), state)


def _cycle_key(subscription_id: str, payment_date: str, renewal_date: str) -> str:
    return f"{subscription_id}:{payment_date}:{renewal_date}"


def is_cycle_renewed(
    state: dict[str, Any], subscription_id: str, payment_date: str, renewal_date: str
) -> bool:
    cycles = state.get(RENEWAL_STATE_KEY) or {}
    return bool(cycles.get(_cycle_key(subscription_id, payment_date, renewal_date)))


def set_cycle_renewed(
    state: dict[str, Any],
    subscription_id: str,
    payment_date: str,
    renewal_date: str,
    renewed: bool,
) -> dict[str, Any]:
    cycles = dict(state.get(RENEWAL_STATE_KEY) or {})
    key = _cycle_key(subscription_id, payment_date, renewal_date)
    if renewed:
        cycles[key] = True
    else:
        cycles.pop(key, None)
    state[RENEWAL_STATE_KEY] = cycles
    return state


def button_window_days(remind_before_days: int) -> int:
    return max(MIN_BUTTON_WINDOW_DAYS, remind_before_days)


def build_button_state(days_left: int, cycle_renewed: bool, remind_before_days: int) -> dict[str, Any]:
    if cycle_renewed:
        return {"kind": "renewed", "label": "已续费", "clickable": True}
    if days_left <= button_window_days(remind_before_days):
        return {"kind": "renewal_pending", "label": f"{days_left}天后续费", "clickable": True}
    return {"kind": "normal", "label": "正常", "clickable": False}


def cleanup_renewal_state(state: dict[str, Any], active_keys: set[str]) -> dict[str, Any]:
    cycles = state.get(RENEWAL_STATE_KEY)
    if not isinstance(cycles, dict):
        return {RENEWAL_STATE_KEY: {}}
    cleaned = {key: value for key, value in cycles.items() if key in active_keys}
    if len(cleaned) != len(cycles):
        return {RENEWAL_STATE_KEY: cleaned}
    return state
