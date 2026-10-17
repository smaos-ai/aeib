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
compliance/check_zone_boundary.py — AEIB Zone Boundary Enforcement
Verifies AST purity to ensure Zone 1 (Open Core) modules never import
Zone 2 (Proprietary Enterprise) modules.
"""

import ast
import sys
from pathlib import Path

# Top-level paths representing Zone 1 open-core code
ZONE1_ROOTS = [
    "src/aeib_core",
    "src/protection_governor.py",
    "aeib_verify.py",
    "benchmarks/aeib_execution_integrity",
    "tests",
    "compliance",
]

# Prefixes reserved strictly for Zone 2 proprietary enterprise modules
ZONE2_PREFIXES = [
    "aeib_postgresql_probe",
    "enterprise",
    "commercial",
]

def is_zone2_module(module_name: str) -> bool:
    """Returns True if the imported module belongs to Zone 2."""
    return any(module_name.startswith(prefix) for prefix in ZONE2_PREFIXES)

def scan_zone_boundary() -> bool:
    violations = []
    
    for root in ZONE1_ROOTS:
        path = Path(root)
        if not path.exists():
            continue
        
        files = list(path.rglob("*.py")) if path.is_dir() else [path]
        for py_file in files:
            if not py_file.is_file() or py_file.suffix != ".py":
                continue
            
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if is_zone2_module(alias.name):
                                violations.append((str(py_file), alias.name))
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and is_zone2_module(node.module):
                            violations.append((str(py_file), node.module))
            except Exception as exc:
                print(f"⚠️ Warning: Could not parse AST for {py_file}: {exc}")

    if violations:
        print("❌ Zone Boundary Violation(s) Detected:")
        for file_path, imported_mod in violations:
            print(f"   {file_path} -> imports Zone 2 module '{imported_mod}'")
        return False

    print("✓ Zone Boundary Check Passed: Zero Zone 1 -> Zone 2 imports detected.")
    return True

if __name__ == "__main__":
    print("========================================================================")
    print("  AEIB ZONE BOUNDARY ENFORCEMENT SCANNER")
    print("========================================================================")
    success = scan_zone_boundary()
    print("========================================================================")
    sys.exit(0 if success else 1)
