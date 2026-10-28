"""Carrier rate functions: name -> function(weight_g, zone) -> cents."""
from __future__ import annotations

from typing import Callable, Dict

CARRIERS: Dict[str, Callable[[int, int], int]] = {}
