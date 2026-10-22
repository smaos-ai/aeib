#!/usr/bin/env python3
"""
Tests for `tools/package_aeib_smf_rc3_release.py` and `scripts/decide_ide_hook.py`.
"""

import json
from pathlib import Path
import tempfile

from scripts.decide_ide_hook import DecideIdeHookEnforcer
from tools.package_aeib_smf_rc3_release import (
    build_signed_rc3_release_bundle,
    verify_signed_rc3_release_bundle,
)


def test_signed_rc3_release_bundle_build_and_cleanroom_verify() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        res = build_signed_rc3_release_bundle(out_dir)
        assert res["cleanroom_files_verified"] >= 20
        assert res["archive_sha256"].startswith("sha256:")
        sig_path = Path(res["signature_file"])
        assert sig_path.exists()
        assert verify_signed_rc3_release_bundle(sig_path) is True

        # Tamper test: modifying statement must fail signature verification
        tampered = json.loads(sig_path.read_text(encoding="utf-8"))
        tampered["statement"]["cleanroom_files_verified"] = 99999
        tampered_path = out_dir / "tampered.sig.json"
        tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
        assert verify_signed_rc3_release_bundle(tampered_path) is False


def test_decide_ide_hook_five_clamps_and_denarration_gate() -> None:
    # 1. Clean execution passes all 5 clamps
    res_ok = DecideIdeHookEnforcer.execute_hook(
        query="/decide storage concurrency",
        candidate_text="Observed 0.000% invalid commit rate under the stated model.",
    )
    assert res_ok["disposition"] == "ALLOW_SYNTHESIS"
    assert res_ok["clamps_evaluated"] == 5
    assert all(res_ok["clamps"].values())

    # 2. Candidate text with a banned promotional word fails Clamp 5 (De-Narration)
    forbidden_word = "bullet" + "proof"
    res_denied = DecideIdeHookEnforcer.execute_hook(
        query="/decide storage concurrency",
        candidate_text=f"This architecture is {forbidden_word}.",
    )
    assert res_denied["disposition"] == "DENIED"
    assert res_denied["halt_code"] == "HALT_EPISTEMIC_DENARRATION_VIOLATION"
    assert forbidden_word in res_denied["violations"]


def test_ide_hook_manifest_exists_and_banned_words_absence() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    hook_json = repo_root / ".agents/hooks/decide_pre_synthesis_hook.json"
    assert hook_json.exists()
    parsed = json.loads(hook_json.read_text(encoding="utf-8"))
    assert parsed["fail_closed"] is True
    assert "slash_command:/decide" in parsed["events"]

    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "proven universal" + "ly",
    ]
    for rel in (
        "tools/package_aeib_smf_rc3_release.py",
        "scripts/decide_ide_hook.py",
        ".agents/hooks/decide_pre_synthesis_hook.json",
        "tests/test_rc3_bundle_and_decide_ide_hook.py",
    ):
        text = (repo_root / rel).read_text(encoding="utf-8").lower()
        for w in banned:
            assert w not in text, f"Forbidden word in {rel}"
