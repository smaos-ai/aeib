"""
tests/test_agent_deception_interlock.py
================================================================================
Test suite for AEIB Track C: Autonomous Deception & Canary Tripwire Defense.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.deception.agent_deception_interlock import (
    AutonomousDeceptionInterlock,
    DecoyTripwire,
)


def test_deception_interlock_nominal_and_tripwire_catches() -> None:
    boundary_priv = Ed25519PrivateKey.generate()
    interlock = AutonomousDeceptionInterlock(boundary_priv)

    # 1. Clean nominal access
    clean_res = interlock.inspect_access_attempt(
        agent_id="agent-legit-01",
        attempted_resource="https://api.stripe.com/v1/charges",
        detected_at=1767225600,
    )
    assert clean_res["disposition"] == "CLEAN"
    assert clean_res["code"] == "OK"
    assert not interlock.is_agent_halted("agent-legit-01")

    # 2. Canary credential bait probe
    bait_res = interlock.inspect_access_attempt(
        agent_id="agent-rogue-02",
        attempted_resource="AKIA_DECOY_ROOT_KEY_991",
        detected_at=1767225601,
    )
    assert bait_res["disposition"] == "HALTED"
    assert bait_res["code"] == "HALT_HONEYPOT_TRIPWIRE_TRIGGERED"
    assert bait_res["tripwire_kind"] == "CANARY_CREDENTIAL"
    assert bait_res["containment"] == "CAPABILITY_REVOKED_AND_HALTED"
    assert interlock.is_agent_halted("agent-rogue-02")
    assert len(interlock.incidents) == 1

    # 3. Subsequent calls from halted agent fail closed immediately
    blocked_res = interlock.inspect_access_attempt(
        agent_id="agent-rogue-02",
        attempted_resource="some_safe_tool",
        detected_at=1767225605,
    )
    assert blocked_res["disposition"] == "HALTED"
    assert blocked_res["code"] == "HALT_AGENT_ALREADY_REVOKED_FOR_DECEPTION_BREACH"

    # 4. Shadow administrative API call
    shadow_api_res = interlock.inspect_access_attempt(
        agent_id="agent-rogue-03",
        attempted_resource="/internal/v1/admin/bypass_gate",
        detected_at=1767225610,
    )
    assert shadow_api_res["disposition"] == "HALTED"
    assert shadow_api_res["code"] == "HALT_HONEYPOT_TRIPWIRE_TRIGGERED"
    assert shadow_api_res["tripwire_kind"] == "SHADOW_API"
    assert interlock.is_agent_halted("agent-rogue-03")

    # 5. Decoy privileged override tool
    tool_res = interlock.inspect_access_attempt(
        agent_id="agent-rogue-04",
        attempted_resource="system.force_override_ceiling",
        detected_at=1767225615,
    )
    assert tool_res["disposition"] == "HALTED"
    assert tool_res["code"] == "HALT_HONEYPOT_TRIPWIRE_TRIGGERED"
    assert tool_res["tripwire_kind"] == "ADMIN_TOOL"
    assert interlock.is_agent_halted("agent-rogue-04")


if __name__ == "__main__":
    test_deception_interlock_nominal_and_tripwire_catches()
    print("TRACK C DECEPTION & HONEYPOT INTERLOCK TESTS PASSED.")
