#!/usr/bin/env python3
r"""
query_memory.py — Query Sovereign Research Memory & Cryptographic Receipts with SQL
Runs zero-egress in-process SQL queries directly over local JSON receipts in <15 ms.
"""

import os
import sys
import argparse

# Add src to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from sovereign_search import SovereignOLAP

DEFAULT_SQL = "SELECT receipt_version, research_session_id, query, disposition, substring(head_hash, 1, 16) as head_prefix, timestamp_utc FROM __RECEIPTS__ ORDER BY timestamp DESC LIMIT 10"

def main():
    parser = argparse.ArgumentParser(description="Query sovereign research receipts using in-process SQL.")
    parser.add_argument("sql", nargs="?", default=DEFAULT_SQL, help="SQL query to execute (use __RECEIPTS__ as table)")
    args = parser.parse_args()

    print("================================================================================")
    print("🔍 SMAOS SOVEREIGN MEMORY SQL QUERY")
    print("================================================================================")
    print(f"Query: {args.sql}\n")
    output = SovereignOLAP.query(args.sql)
    print(output)
    print("================================================================================")

if __name__ == "__main__":
    main()
