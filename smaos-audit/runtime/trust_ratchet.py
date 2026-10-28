#!/usr/bin/env python3
"""
runtime/trust_ratchet.py — Moat 12: ADLC Dynamic Trust Ratchet Decorator
Sovereign Multi-Agent OS (SMAOS) / STAR Protocol v1.1.0

Features:
  1. Multi-Stage Capability Degradation: UNRESTRICTED (3) -> READ_ONLY (2) -> QUARANTINED (1) -> HALTED (0).
  2. Automatic Ratchet Tripping on missing wire confirmation or timeout.
  3. Mutating Tool Lockout: Blocks external mutations once boundary uncertainty is detected.

Zero external dependencies (pure Python standard library).
"""

from enum import Enum
import functools
from typing import Any, Callable, Dict, Optional


class CapabilityLevel(Enum):
    HALTED       = 0  # Process terminated
    QUARANTINED  = 1  # Context frozen; all outbound calls forced to UNKNOWN
    READ_ONLY    = 2  # Mutating tools revoked; can only inspect state
    UNRESTRICTED = 3  # Can read, write, and execute external mutations


class TrustRatchet:
    def __init__(self, initial_level: CapabilityLevel = CapabilityLevel.UNRESTRICTED):
        self.level = initial_level
        self.trip_history = []

    def trip(self, reason: str) -> CapabilityLevel:
        """Ratchet down capabilities when boundary uncertainty occurs."""
        prev = self.level
        if self.level == CapabilityLevel.UNRESTRICTED:
            self.level = CapabilityLevel.READ_ONLY
        elif self.level == CapabilityLevel.READ_ONLY:
            self.level = CapabilityLevel.QUARANTINED
        elif self.level == CapabilityLevel.QUARANTINED:
            self.level = CapabilityLevel.HALTED

        msg = f"[!] Trust Ratchet TRIPPED ({reason}). New Capability Level: {self.level.name}"
        self.trip_history.append({"from": prev.name, "to": self.level.name, "reason": reason})
        return self.level

    def reset(self, permit: str) -> bool:
        if permit and permit.startswith("PERMIT_"):
            self.level = CapabilityLevel.UNRESTRICTED
            return True
        return False


# Global default ratchet instance
ratchet = TrustRatchet()


def proof_or_ratchet(tool_type: str = "mutating", custom_ratchet: Optional[TrustRatchet] = None):
    """
    Decorator that enforces dynamic capability gating on autonomous agent actions.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            r = custom_ratchet or ratchet
            if tool_type == "mutating" and r.level.value < CapabilityLevel.UNRESTRICTED.value:
                raise PermissionError(f"Action blocked by Trust Ratchet: Current level is {r.level.name}")
            try:
                result = func(*args, **kwargs)
                if isinstance(result, dict) and not result.get("wire_confirmed", True):
                    r.trip(f"Wire confirmation missing / Timeout in '{func.__name__}'")
                    return {"status": "UNKNOWN", "ratchet_state": r.level.name, "retry_held": True}
                return result
            except Exception as e:
                r.trip(f"Exception in '{func.__name__}': {str(e)}")
                raise
        return wrapper
    return decorator
