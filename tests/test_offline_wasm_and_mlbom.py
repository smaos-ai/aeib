#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
tests/test_offline_wasm_and_mlbom.py — Tests for CycloneDX ML-BOM & Offline WASM Verifier
"""

import os
import subprocess
import tempfile
from pathlib import Path
import pytest

from tools.cyclonedx_mlbom_generator import generate_cyclonedx_mlbom


def test_cyclonedx_mlbom_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "test_mlbom.json")
        bom = generate_cyclonedx_mlbom(output_path=out_path)
        assert bom["bomFormat"] == "CycloneDX"
        assert bom["specVersion"] == "1.6"
        assert len(bom["components"]) >= 5
        assert os.path.exists(out_path)

        # Check model component properties
        hy_mt2 = next(c for c in bom["components"] if c["name"] == "Tencent Hy-MT2")
        assert hy_mt2["type"] == "machine-learning-model"
        assert hy_mt2["modelCard"]["modelParameters"]["task"] == "translation-and-intent-classification"


def test_offline_wasm_binary_and_node_acceptance():
    wasm_path = Path("smaos_verify.wasm")
    assert wasm_path.exists(), "smaos_verify.wasm binary must exist in repo root"
    assert wasm_path.stat().st_size > 150_000, "WASM binary must be ~195 KB"

    # Execute Node test suite
    res = subprocess.run(
        ["node", "tests/test_smaos_verify_wasm.js"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.returncode == 0, f"Node WASM tests failed:\n{res.stderr}\n{res.stdout}"
    assert "ALL REAL WASM ACCEPTANCE TESTS PASSED" in res.stdout


def test_banned_words_absence_in_mlbom_generator():
    for fpath in ["tools/cyclonedx_mlbom_generator.py", "tests/test_offline_wasm_and_mlbom.py"]:
        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read().lower()
        forbidden = [
            "guaran" + "tee",
            "bullet" + "proof",
            "enterprise-" + "grade",
            "production-" + "safe",
            "100% " + "secure",
            "unassail" + "able",
        ]
        for word in forbidden:
            assert word not in text, f"Banned word '{word}' found in {fpath}"
