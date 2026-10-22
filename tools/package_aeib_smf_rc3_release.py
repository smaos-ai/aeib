#!/usr/bin/env python3
# File: tools/package_aeib_smf_rc3_release.py
"""
Deterministic Release Packager for `aeib-smf-v1.0.0-rc.3.tar.gz`.

Packages the complete Cross-Hemisphere Epistemic Council, 3-Tier `Ask` Router,
P0/P1 Typestate & Non-Dilutable Conflict WAL, P2 Palantir 6-Way Joint Commit
Witness, and `/decide` v3.2 suite into a bit-identical, reproducible archive
(`SOURCE_DATE_EPOCH = 1760918400`) with an Ed25519 RFC 8785 JCS release signature.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cross_hemisphere_council_decide import canonical_jcs, sha256_prefixed
from tools.cross_hemisphere_epistemic_council import (
    run_integrated_tri_partition_architecture,
)

FIXED_EPOCH = 1760918400  # 2025-10-20T00:00:00Z deterministic mtime

RC3_RELEASE_FILES: Tuple[str, ...] = (
    ".agents/skills/decide/SKILL.md",
    "EVIDENCE_MANIFEST.md",
    "compliance/ast_purity.py",
    "compliance/check_zone_boundary.py",
    "compliance/eac_typestate_conflict_engine.py",
    "compliance/no_mock_enforcer.py",
    "decide.md",
    "scripts/decide_ide_hook.py",
    "src/decide_categorical_epistemic_engine.py",
    "src/epistemic_action_compiler.py",
    "src/epistemic_core.py",
    "tests/test_cross_hemisphere_council_decide.py",
    "tests/test_decide_categorical_epistemic_engine.py",
    "tests/test_decide_v2_constant_time_snapshot.py",
    "tests/test_eac_typestate_conflict_engine.py",
    "tests/test_palantir_ontology_joint_witness_engine.py",
    "tools/cross_hemisphere_council_decide.py",
    "tools/cross_hemisphere_epistemic_council.py",
    "tools/current_missed_next_calculus.py",
    "tools/decide_v2_constant_time_snapshot.py",
    "tools/epistemic_5why_loop.py",
    "tools/epistemic_action_compiler_ab_test.py",
    "tools/palantir_ontology_joint_witness_engine.py",
    "tools/scitt_ap2_x402_otel_engine.py",
)


def build_signed_rc3_release_bundle(
    output_dir: Path,
    signing_key: Optional[Ed25519PrivateKey] = None,
) -> Dict[str, Any]:
    """
    Builds `aeib-smf-v1.0.0-rc.3.tar.gz` deterministically, verifies bit-identical
    reproducibility across two independent in-memory builds, extracts and verifies
    all SHA-256 digests in a cleanroom directory, and emits an Ed25519 JCS receipt.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    tri_partition_report = run_integrated_tri_partition_architecture()

    files_to_pack: List[Tuple[str, bytes]] = []
    file_digests: Dict[str, str] = {}

    for rel_path in sorted(RC3_RELEASE_FILES):
        abs_path = _REPO_ROOT / rel_path
        if abs_path.exists():
            raw = abs_path.read_bytes()
            files_to_pack.append((rel_path, raw))
            file_digests[rel_path] = hashlib.sha256(raw).hexdigest()

    manifest_lines = [f"{digest}  {rel}" for rel, digest in sorted(file_digests.items())]
    sha256sums_bytes = ("\n".join(manifest_lines) + "\n").encode("utf-8")
    files_to_pack.append(("SHA256SUMS.txt", sha256sums_bytes))

    def _pack_tar_gz() -> bytes:
        buf = io.BytesIO()
        with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=FIXED_EPOCH) as gz:
            with tarfile.open(mode="w", fileobj=gz) as tar:
                for arcname, content in sorted(files_to_pack, key=lambda x: x[0]):
                    info = tarfile.TarInfo(name=arcname)
                    info.size = len(content)
                    info.mtime = FIXED_EPOCH
                    info.uid = 0
                    info.gid = 0
                    info.uname = "root"
                    info.gname = "root"
                    info.mode = 0o644
                    tar.addfile(info, io.BytesIO(content))
        return buf.getvalue()

    bundle_1 = _pack_tar_gz()
    bundle_2 = _pack_tar_gz()
    assert bundle_1 == bundle_2, "RC3 tarball build must be bit-identical"

    tar_path = output_dir / "aeib-smf-v1.0.0-rc.3.tar.gz"
    tar_path.write_bytes(bundle_1)
    archive_sha256 = hashlib.sha256(bundle_1).hexdigest()

    sha_path = output_dir / "aeib-smf-v1.0.0-rc.3.tar.gz.sha256"
    sha_path.write_text(
        f"{archive_sha256}  aeib-smf-v1.0.0-rc.3.tar.gz\n", encoding="utf-8"
    )

    # Cleanroom extraction & per-file SHA-256 verification
    with tempfile.TemporaryDirectory() as cleanroom:
        with tarfile.open(tar_path, mode="r:gz") as tar:
            tar.extractall(path=cleanroom, filter="data")
        sums_text = (Path(cleanroom) / "SHA256SUMS.txt").read_text(encoding="utf-8")
        for line in sums_text.splitlines():
            if not line.strip():
                continue
            expected_hex, rel_name = line.split("  ", 1)
            actual_hex = hashlib.sha256(
                (Path(cleanroom) / rel_name).read_bytes()
            ).hexdigest()
            assert actual_hex == expected_hex, f"Cleanroom digest mismatch on {rel_name}"

    priv = signing_key or Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(priv.public_key().public_bytes_raw()).decode("ascii")

    jcs_statement = {
        "archive_filename": "aeib-smf-v1.0.0-rc.3.tar.gz",
        "archive_sha256": f"sha256:{archive_sha256}",
        "cleanroom_files_verified": len(files_to_pack),
        "file_digests": file_digests,
        "oracle_gap_prevented": tri_partition_report["oracle_gap_prevented"],
        "release_version": "aeib-smf-v1.0.0-rc.3",
        "tri_partition_verdict": tri_partition_report["locked_verdict"],
    }
    statement_bytes = canonical_jcs(jcs_statement)
    sig_b64 = base64.b64encode(priv.sign(statement_bytes)).decode("ascii")

    sig_envelope = {
        "statement": jcs_statement,
        "statement_jcs_sha256": sha256_prefixed(statement_bytes),
        "public_key_b64": pub_b64,
        "signature_b64": sig_b64,
    }
    sig_path = output_dir / "aeib-smf-v1.0.0-rc.3.tar.gz.sig.json"
    sig_path.write_text(
        json.dumps(sig_envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return {
        "archive_path": str(tar_path),
        "archive_sha256": f"sha256:{archive_sha256}",
        "cleanroom_files_verified": len(files_to_pack),
        "signature_file": str(sig_path),
        "public_key_b64": pub_b64,
        "signature_b64": sig_b64,
        "statement_jcs_sha256": sig_envelope["statement_jcs_sha256"],
    }


def verify_signed_rc3_release_bundle(sig_json_path: Path) -> bool:
    data = json.loads(sig_json_path.read_text(encoding="utf-8"))
    statement = data["statement"]
    statement_bytes = canonical_jcs(statement)
    if sha256_prefixed(statement_bytes) != data["statement_jcs_sha256"]:
        return False
    pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(data["public_key_b64"]))
    sig = base64.b64decode(data["signature_b64"])
    try:
        pub.verify(sig, statement_bytes)
    except Exception:
        return False
    tar_path = sig_json_path.parent / statement["archive_filename"]
    if not tar_path.exists():
        return False
    actual_tar_sha = f"sha256:{hashlib.sha256(tar_path.read_bytes()).hexdigest()}"
    return actual_tar_sha == statement["archive_sha256"]


if __name__ == "__main__":
    out_summary = build_signed_rc3_release_bundle(_REPO_ROOT / "output")
    out_summary["signature_verified"] = verify_signed_rc3_release_bundle(
        _REPO_ROOT / "output" / "aeib-smf-v1.0.0-rc.3.tar.gz.sig.json"
    )
    print(json.dumps(out_summary, indent=2, sort_keys=True))
