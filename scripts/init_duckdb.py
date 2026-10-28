#!/usr/bin/env python3
r"""
init_duckdb.py — Initializes Zero-Egress In-Process OLAP Database (DuckDB / chDB)
Configures direct schema-on-read views over JSONL research logs and cryptographic receipts.
"""

import os
import sys
from pathlib import Path

# Add src to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from sovereign_search import SovereignOLAP

def init_research_olap():
    log_path = Path("antigravity/research_log.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        log_path.touch()

    receipts_dir = Path("provenance/receipts")
    receipts_dir.mkdir(parents=True, exist_ok=True)

    print("================================================================================")
    print("📊 SMAOS SOVEREIGN OLAP INITIALIZER (DuckDB / chDB)")
    print("================================================================================")

    # Test OLAP query over receipts
    sql = "SELECT receipt_version, disposition, count() as total_receipts FROM __RECEIPTS__ GROUP BY receipt_version, disposition"
    result = SovereignOLAP.query(sql)
    print("✅ Sovereign OLAP Engine Initialized Successfully.")
    print("   Target Log:     antigravity/research_log.jsonl")
    print("   Target Receipts: provenance/receipts/*.json")
    print("\n[CURRENT RECEIPT LEDGER ROLL-UP]:")
    print(result)
    print("================================================================================")
    print("💡 Query anytime via: python3 scripts/query_memory.py [optional_sql]")
    print("================================================================================")

if __name__ == "__main__":
    init_research_olap()
