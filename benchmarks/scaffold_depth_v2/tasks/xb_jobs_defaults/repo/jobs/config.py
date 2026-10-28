"""Job configuration: user overrides merged over package defaults."""
from __future__ import annotations

from typing import Any, Dict, Optional

DEFAULTS: Dict[str, Any] = {
    "queue": "default",
    "timeout_s": 30,
    "retry": {"max_attempts": 3, "backoff_ms": 200, "multiplier": 2},
}


def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge `override` into `base` (nested dicts are merged key by key)."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def validate(cfg: Dict[str, Any]) -> Dict[str, Any]:
    retry = cfg["retry"]
    if not isinstance(retry.get("max_attempts"), int) or retry["max_attempts"] < 1:
        raise ValueError("retry.max_attempts must be an int >= 1")
    if retry.get("backoff_ms", 0) < 0 or retry.get("multiplier", 1) < 1:
        raise ValueError("invalid backoff settings")
    if cfg.get("timeout_s", 1) <= 0:
        raise ValueError("timeout_s must be positive")
    return cfg


def load_config(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a fresh configuration: DEFAULTS with `overrides` merged in."""
    cfg = dict(DEFAULTS)
    return validate(_merge(cfg, overrides or {}))
