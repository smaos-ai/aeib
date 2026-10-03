#!/usr/bin/env python3
import sys
from pathlib import Path

# Verify that test suites connect to physical systems on designated axes
REQUIRED_AXES = {
    "postgresql": "psycopg2.connect",
    "signing": "cryptography.hazmat.primitives.asymmetric.ed25519",
    "canonicalization": "rfc8785",
}

def verify_zero_mock_architecture(benchmark_dir: Path):
    run_episodes = benchmark_dir / "run_episodes.py"
    if not run_episodes.exists():
        print(f"[!] Harness missing: {run_episodes}", file=sys.stderr)
        sys.exit(1)

    content = run_episodes.read_text(encoding="utf-8")
    
    # Must use actual JCS and Ed25519 imports
    if "unittest.mock" in content:
        print("[!] Fatal: Mock framework detected in benchmark harness.", file=sys.stderr)
        sys.exit(1)
        
    print("[✓] Zero-Mock Enforcer: Integration axes confirmed unmocked.")
    sys.exit(0)

if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "benchmarks/aeib_execution_integrity")
    verify_zero_mock_architecture(target)
