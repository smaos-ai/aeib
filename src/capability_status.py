"""Shared capability-status vocabulary for simulated / scaffold modules.

Rule enforced by every module that imports this helper: anything that is not a
real execution against a real capability (Lean kernel, TPM, TEE device, BPF
kernel maps, a sound zero-knowledge proof system, a speech model, ...) must be
an explicit, visible OPT-IN and must never be reported as a default success.

Opt-in sources, in priority order:
  1. an explicit ``allow_simulation=True`` / ``False`` argument at the call site;
  2. otherwise the environment variable ``AEIB_ALLOW_SIMULATION`` set to ``"1"``.

``AEIB_ALLOW_SIMULATION`` is intentionally NOT exported by any repository
script or hook; it exists for an operator who knowingly wants the simulated
path on a developer workstation.
"""

from __future__ import annotations

import os
from typing import Optional

SIMULATION_ENV = "AEIB_ALLOW_SIMULATION"

ERR_CAPABILITY_UNAVAILABLE_ON_HOST = "ERR_CAPABILITY_UNAVAILABLE_ON_HOST"

# Status vocabulary (string constants so they serialize into JSON receipts).
REAL_EXECUTED = "REAL_EXECUTED"
"""A real tool / kernel / device was executed and its result was checked."""

SIMULATED_OPT_IN = "SIMULATED_OPT_IN"
"""A software model ran because the caller explicitly opted in to simulation."""

TEXT_LINT_ONLY = "TEXT_LINT_ONLY"
"""Only textual / structural linting ran; no semantic checker was executed."""

NOT_EXECUTED = "NOT_EXECUTED"
"""Nothing was executed (capability absent and no simulation opt-in)."""

ALL_STATUSES = (REAL_EXECUTED, SIMULATED_OPT_IN, TEXT_LINT_ONLY, NOT_EXECUTED)


def simulation_allowed(explicit: Optional[bool] = None) -> bool:
    """Return True only on an explicit opt-in.

    An explicit boolean argument wins. When ``explicit`` is None the
    environment variable ``AEIB_ALLOW_SIMULATION`` must equal ``"1"``.
    """
    if explicit is not None:
        return bool(explicit)
    return os.environ.get(SIMULATION_ENV, "") == "1"


class CapabilityUnavailableError(RuntimeError):
    """Raised when a real capability is absent and simulation was not opted in."""

    code = ERR_CAPABILITY_UNAVAILABLE_ON_HOST

    def __init__(self, capability: str, detail: str = "") -> None:
        self.capability = capability
        self.detail = detail
        msg = (
            f"[{ERR_CAPABILITY_UNAVAILABLE_ON_HOST}] {capability}: real capability not "
            f"executed on this host and simulation was not opted in "
            f"(pass allow_simulation=True or set {SIMULATION_ENV}=1)."
        )
        if detail:
            msg = f"{msg} {detail}"
        super().__init__(msg)


def require_simulation_opt_in(
    capability: str, explicit: Optional[bool] = None, detail: str = ""
) -> str:
    """Return ``SIMULATED_OPT_IN`` if opted in, else raise CapabilityUnavailableError."""
    if not simulation_allowed(explicit):
        raise CapabilityUnavailableError(capability, detail)
    return SIMULATED_OPT_IN
