from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.log_store import read_json, write_json_atomic


MIN_BUTTON_WINDOW_DAYS = 7


def _state_path(data_dir: Path) -> Path:
    return data_dir / "renewal_state.json"


def load_renewal_state(data_dir: Path) -> dict[str, Any]:
    data = read_json(_state_path(data_dir), {})
    # 兼容旧结构 { "renewed_cycles": { ... } }
    if "renewed_cycles" in data and isinstance(data["renewed_cycles"], dict):
        return dict(data["renewed_cycles"])
    return data if isinstance(data, dict) else {}


def save_renewal_state(data_dir: Path, state: dict[str, Any]) -> None:
    write_json_atomic(_state_path(data_dir), state)


def _cycle_key(subscription_id: str, payment_date: str, renewal_date: str) -> str:
    return f"{subscription_id}:{payment_date}:{renewal_date}"


def is_cycle_renewed(
    state: dict[str, Any], subscription_id: str, payment_date: str, renewal_date: str
) -> bool:
    return bool(state.get(_cycle_key(subscription_id, payment_date, renewal_date)))


def set_cycle_renewed(
    state: dict[str, Any],
    subscription_id: str,
    payment_date: str,
    renewal_date: str,
    renewed: bool,
) -> dict[str, Any]:
    key = _cycle_key(subscription_id, payment_date, renewal_date)
    if renewed:
        state[key] = True
    else:
        state.pop(key, None)
    return state


def button_window_days(remind_before_days: int) -> int:
    return max(MIN_BUTTON_WINDOW_DAYS, remind_before_days)


def build_button_state(days_left: int, cycle_renewed: bool, remind_before_days: int) -> dict[str, Any]:
    if cycle_renewed:
        return {"kind": "renewed", "label": "已续费", "clickable": True}
    if days_left <= button_window_days(remind_before_days):
        return {"kind": "renewal_pending", "label": f"{days_left}天后续费", "clickable": True}
    return {"kind": "normal", "label": "正常", "clickable": False}


def build_toggle_response(days_left: int, renewed: bool, remind_before_days: int) -> dict[str, Any]:
    return build_button_state(days_left, renewed, remind_before_days) | {"renewed": renewed}


def cleanup_renewal_state(state: dict[str, Any], active_keys: set[str]) -> dict[str, Any]:
    cleaned = {key: value for key, value in state.items() if key in active_keys}
    if len(cleaned) != len(state):
        return cleaned
    return state
