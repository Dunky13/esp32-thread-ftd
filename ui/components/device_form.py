from __future__ import annotations

from html import escape
from typing import Any


def value(defaults: dict[str, Any], key: str, fallback: object) -> str:
    return escape(str(defaults.get(key, fallback)))

