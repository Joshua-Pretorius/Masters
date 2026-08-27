from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def slug(value: str, *, upper: bool = False) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_")
    return cleaned.upper() if upper else cleaned


def strip_safe(value: str) -> str:
    return value.strip().removesuffix(".SAFE")


def parse_delta_hours(value: str | float | int) -> float:
    if isinstance(value, (float, int)):
        return float(value)
    numbers = [float(token) for token in re.findall(r"[+-]?\d+(?:\.\d+)?", value or "")]
    if not numbers:
        raise ValueError(f"No hour value in {value!r}")
    return sum(numbers) / len(numbers)


def delta_label(delta_hours: float) -> str:
    if abs(delta_hours) < 0.005:
        return "SAR and optical acquisition at the same time"
    relation = "AFTER" if delta_hours > 0 else "BEFORE"
    return f"SAR {abs(delta_hours):.2f} h {relation} optical"


def iso_utc(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = text.replace(" UTC", "Z").replace(" ", "T")
    if text.endswith("Z"):
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    else:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_hash(*parts: object, length: int = 12) -> str:
    payload = "\0".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:length]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def relative_to_root(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()
