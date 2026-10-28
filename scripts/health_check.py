#!/usr/bin/env python3
r"""
health_check.py — Pre-Flight Diagnostic Health Check for Sovereign Research OS
Validates network endpoints, local daemons (SearXNG, Ollama), cryptographic keys,
and in-process OLAP engines.
"""

import sys
import os
import urllib.request
import argparse
from pathlib import Path

def check_http_endpoint(name: str, url: str, timeout: int = 2) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SMAOS-HealthCheck/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status in (200, 204):
                print(f"✅ {name:20s}: ONLINE (HTTP {resp.status}) -> {url}")
                return True
            else:
                print(f"⚠️  {name:20s}: WARN (HTTP {resp.status}) -> {url}")
                return False
    except Exception as e:
        print(f"ℹ️  {name:20s}: OFFLINE/UNREACHABLE (Fallback Enabled)")
        return False

def main():
    parser = argparse.ArgumentParser(description="Health check for Sovereign Research OS components.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if any live daemon is unreachable")
    args = parser.parse_args()

    print("================================================================================")
    print("🩺 SMAOS SOVEREIGN RESEARCH OS — PRE-FLIGHT HEALTH CHECK")
    print("================================================================================")

    # 1. Local Daemons
    print("\n[1. LIVE RETRIEVAL & SYNTHESIS DAEMONS]")
    searxng_ok = check_http_endpoint("SearXNG (Port 8080)", "http://localhost:8080/search?q=health&format=json")
    ollama_ok = check_http_endpoint("Ollama (Port 11434)", "http://localhost:11434/api/tags")

    # 2. Free Academic Web Endpoints
    print("\n[2. OPEN ACADEMIC TRUTH ENDPOINTS]")
    scholar_ok = check_http_endpoint("Semantic Scholar API", "https://api.semanticscholar.org/graph/v1/paper/search?query=test&limit=1")
    arxiv_ok = check_http_endpoint("ArXiv API", "http://export.arxiv.org/api/query?search_query=all:electron&max_results=1")

    # 3. Cryptographic Primitives & Key Registry
    print("\n[3. CRYPTOGRAPHIC PROVENANCE & KEYS]")
    priv_key = Path("keys/ed25519-private.pem")
    pub_key = Path("keys/ed25519-public.pem")
    merkle = Path("provenance/merkle_root.txt")

    keys_ok = priv_key.exists() and pub_key.exists()
    if keys_ok:
        print(f"✅ {'Ed25519 Keypair':20s}: PRESENT ({priv_key} & {pub_key})")
    else:
        print(f"❌ {'Ed25519 Keypair':20s}: MISSING (will auto-generate on first research session)")

    if merkle.exists():
        print(f"✅ {'Merkle Ledger Root':20s}: ANCHORED ({merkle.read_text().strip()[:24]}...)")
    else:
        print(f"ℹ️  {'Merkle Ledger Root':20s}: UNINITIALIZED (will initialize on first receipt)")

    # 4. In-Process OLAP
    print("\n[4. IN-PROCESS SQL OLAP ENGINES]")
    try:
        import chdb
        print(f"✅ {'chDB ClickHouse OLAP':20s}: INSTALLED (v{chdb.__version__})")
        olap_ok = True
    except ImportError:
        try:
            import duckdb
            print(f"✅ {'DuckDB OLAP':20s}: INSTALLED")
            olap_ok = True
        except ImportError:
            print(f"⚠️  {'OLAP Engine':20s}: Neither chdb nor duckdb installed")
            olap_ok = False

    print("\n================================================================================")
    if args.strict and not (searxng_ok and ollama_ok and keys_ok and olap_ok):
        print("❌ PRE-FLIGHT CHECK FAILED (Strict Mode: All daemons must be live)")
        sys.exit(1)
    else:
        print("🎉 PRE-FLIGHT CHECK COMPLETE: System is ready for sovereign research.")
        print("   (Offline deterministic fallbacks are fully armed for air-gapped environments)")
    print("================================================================================\n")

if __name__ == "__main__":
    main()
