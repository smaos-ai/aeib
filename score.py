#!/usr/bin/env python3
"""
Agent-Effect Integrity Benchmark (AEIB) v0.1 — Score Entrypoint
Compares evaluation dispositions against expected golden scorecards.

Usage:
  python3 score.py
"""
import sys
from pathlib import Path

# Ensure benchmark root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runner.scorer import main

if __name__ == "__main__":
    main()
