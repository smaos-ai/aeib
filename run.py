#!/usr/bin/env python3
"""
Agent-Effect Integrity Benchmark (AEIB) v0.1 — Run Entrypoint
Executes scenario fixtures against normative precedence:
  INVALID_INPUT -> MISSING_EVIDENCE -> CONFLICT -> REFUSED -> CONFIRMED -> UNKNOWN

Usage:
  python3 run.py fixtures/
  python3 run.py fixtures/02_timeout_unknown.jsonl [out/results.json]
"""
import sys
from pathlib import Path

# Ensure benchmark root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runner.reference_runner import main

if __name__ == "__main__":
    main()
