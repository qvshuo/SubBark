"""Atomic JSON persistence helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


def read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default.copy()


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
        temporary_name = file.name
    os.replace(temporary_name, path)


def trim_notifications(path: Path, max_entries: int = 1000) -> None:
    data = read_json(path, {"notifications": []})
    notifications = data.get("notifications", [])
    if isinstance(notifications, list) and len(notifications) > max_entries:
        data["notifications"] = notifications[-max_entries:]
        write_json_atomic(path, data)
