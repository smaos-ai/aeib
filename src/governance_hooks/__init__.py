"""
SMAOS Layer 6: Governance Hooks
Colibri RCE pre-execution approval with fail-closed semantics
"""

from src.governance_hooks.colibri_rce_check import (
    app,
    ColibriGovernanceGate,
    RCECheckRequest,
    RCECheckResponse,
    start_governance_server,
)

__all__ = [
    "app",
    "ColibriGovernanceGate",
    "RCECheckRequest",
    "RCECheckResponse",
    "start_governance_server",
]

# Startup hook message
import logging

logger = logging.getLogger(__name__)
logger.info("Colibri RCE governance gate ACTIVE")
