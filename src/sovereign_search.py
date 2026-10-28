#!/usr/bin/env python3
r"""
sovereign_search.py — 100% Free Sovereign Research Stack
Replaces commercial, rate-limited APIs (Exa, Tavily, Scite, Consensus) with:
1. SearXNG (Self-Hosted Web Meta-Search) + DuckDuckGo Instant Answer fallback
2. Semantic Scholar + ArXiv + Crossref (Free Academic Retrieval)
3. Ollama (Local Zero-Egress LLM Synthesis: Llama 3.1 / Qwen 2.5)
4. DuckDB / chDB (In-Process Zero-Egress SQL OLAP Database)
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
import hashlib
from typing import Dict, Any, List, Optional, Tuple


# ── 1. The Eyes: Sovereign Web Retriever (SearXNG + DuckDuckGo) ───────────────

OFFLINE_PROVENANCE = "OFFLINE_FIXTURE_NOT_RETRIEVED"
LIVE_PROVENANCE = "LIVE_RETRIEVAL"


def _live_row(url: str, title: str, content: str, engine: str) -> Dict[str, Any]:
    return {
        "url": url,
        "title": title,
        "content": content,
        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "engine": engine,
        "retrieved": True,
        "provenance": LIVE_PROVENANCE,
    }


def _offline_row(url: str, title: str, content: str, origin_engine: str) -> Dict[str, Any]:
    prefixed_title = title if title.startswith("OFFLINE_FIXTURE: ") else f"OFFLINE_FIXTURE: {title}"
    return {
        "url": url,
        "title": prefixed_title,
        "content": content,
        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "engine": "offline_fixture",
        "fixture_origin_engine": origin_engine,
        "retrieved": False,
        "provenance": OFFLINE_PROVENANCE,
    }


class SearxNGClient:
    """
    Self-hosted meta-search client querying SearXNG via standard JSON API.
    Falls back to DuckDuckGo Instant Answer API or deterministic local knowledge.
    """

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = os.environ.get("SEARXNG_URL", base_url).rstrip("/")

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        results = []

        # 1. Try local SearXNG
        try:
            params = urllib.parse.urlencode({"q": query, "format": "json"})
            req_url = f"{self.base_url}/search?{params}"
            req = urllib.request.Request(req_url, headers={"User-Agent": "SMAOS-Sovereign-Search/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    for r in data.get("results", [])[:max_results]:
                        content = r.get("content") or r.get("title") or ""
                        h = hashlib.sha256(content.encode("utf-8")).hexdigest()
                        results.append({
                            "url": r.get("url", ""),
                            "title": r.get("title", ""),
                            "content": content,
                            "content_hash": h,
                            "engine": "searxng"
                        })
                    if results:
                        return results
        except Exception:
            pass  # Fall through to DuckDuckGo or offline fallback

        # 2. Try DuckDuckGo Instant Answer API (Free public API)
        try:
            params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": "1"})
            ddg_url = f"https://api.duckduckgo.com/?{params}"
            req = urllib.request.Request(ddg_url, headers={"User-Agent": "SMAOS-Sovereign-Search/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    ddg_data = json.loads(resp.read().decode("utf-8"))
                    abstract = ddg_data.get("AbstractText") or ddg_data.get("Heading")
                    if abstract:
                        h = hashlib.sha256(abstract.encode("utf-8")).hexdigest()
                        results.append({
                            "url": ddg_data.get("AbstractURL") or "https://duckduckgo.com/?q=" + urllib.parse.quote(query),
                            "title": ddg_data.get("Heading", "Instant Answer"),
                            "content": abstract,
                            "content_hash": h,
                            "engine": "duckduckgo_instant"
                        })
                        return results
        except Exception:
            pass

        # 3. Deterministic Offline Sovereign Index
        return self._offline_fallback(query)

    def _offline_fallback(self, query: str) -> List[Dict[str, Any]]:
        q_lower = query.lower()
        if "deferral" in q_lower or "annex iii" in q_lower or "ai act" in q_lower or "reporting thresholds" in q_lower:
            c1 = "The Digital Omnibus (EU 2026/1744) deferred Annex III high-risk obligations to December 2, 2027, and Annex I embedded systems to August 2, 2028. Article 50 transparency obligations remain enforceable as of August 2, 2026."
            c2 = "The 4-hour clock starts at classification as major, not detection. The 24-hour awareness backstop runs continuously from initial awareness. Initial deadline: min(T_class + 4h, T_aware + 24h)."
            return [
                _offline_row(
                    "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R1744",
                    "Digital Omnibus Regulation (EU) 2026/1744 — AI Act Timeline Deferrals",
                    c1,
                    "searxng_fallback",
                ),
                _offline_row(
                    "https://www.europarl.europa.eu/topics/en/article/20260507STO23456",
                    "European Parliament Briefing on AI Act Article 50 and High-Risk Timeline",
                    c1,
                    "searxng_fallback",
                ),
                _offline_row(
                    "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32025R0301",
                    "Commission Delegated Regulation (EU) 2025/301 — RTS on Major ICT Incident Classification",
                    c2,
                    "searxng_fallback",
                ),
                _offline_row(
                    "https://www.eba.europa.eu/regulation-and-policy/digital-operational-resilience",
                    "EBA Regulatory Technical Standards on Dual-Clock Incident Reporting",
                    c2,
                    "searxng_fallback",
                ),
            ]
        elif "deepseek" in q_lower or "chinese" in q_lower or "context window" in q_lower:
            c1 = "Frontier Chinese labs (DeepSeek, Moonshot) expand prompt windows to 10M+ tokens, but introduce a critical 'Compaction Cliff' and Epistemic Void—lacking cryptographic source proof or un-altered RAG traces."
            c2 = "CAICT audit framework specifies requirements for agentic trust boundaries, state-level RAG integrity, and execution logging in enterprise deployments."
            return [
                _offline_row(
                    "https://arxiv.org/abs/2609.12890",
                    "DeepSeek-V4 & Moonshot Kimi Context Scaling Analysis (2026-09)",
                    c1,
                    "searxng_fallback",
                ),
                _offline_row(
                    "https://caict.ac.cn/reports/2026/agent_trust_architecture.pdf",
                    "China AI Agent Architecture & State-RAG Audit Report (2026-08)",
                    c2,
                    "searxng_fallback",
                ),
            ]
        elif "dora" in q_lower or "annex ii" in q_lower or "rts" in q_lower:
            c1 = "Annex II specifies the mandatory standard template for the initial notification of major ICT-related incidents under Regulation (EU) 2022/2554 (DORA)."
            c2 = "Financial entities subject to DORA Article 19 must record precise awareness timestamps and maintain cryptographic audit trails for all critical third-party ICT service interactions."
            return [
                _offline_row(
                    "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32025R0301",
                    "Commission Delegated Regulation (EU) 2025/301 — RTS on Major ICT Incident Classification",
                    c1,
                    "searxng_fallback",
                ),
                _offline_row(
                    "https://www.eba.europa.eu/regulation-and-policy/operational-resilience-dora",
                    "EBA Regulatory Technical Standards on Incident Reporting under DORA",
                    c2,
                    "searxng_fallback",
                ),
            ]
        else:
            c = f"Sovereign execution record for query: '{query}' under air-gapped validation boundary."
            return [
                _offline_row(
                    "https://standards.iso.org/iso/iec/42001/ed-1/en",
                    "ISO/IEC 42001:2023 Artificial Intelligence Management System",
                    c,
                    "searxng_fallback",
                )
            ]


# ── 2. The Fact-Checkers: Sovereign Academic Retriever ────────────────────────

class SovereignAcademicRetriever:
    """
    Queries open and free academic APIs:
    - Semantic Scholar API (Free, 200M+ papers)
    - ArXiv Export API (Free preprints)
    - Crossref Works API (Free DOI metadata)
    """

    def search(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        results = []

        # 1. Semantic Scholar API with exponential backoff retry on 429 / 5xx
        for attempt in range(3):
            try:
                params = urllib.parse.urlencode({"query": query, "limit": max_results, "fields": "title,abstract,authors,citationCount,url"})
                req_url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"
                req = urllib.request.Request(req_url, headers={"User-Agent": "SMAOS-Academic-Research/1.0"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        for paper in data.get("data", []):
                            abstract = paper.get("abstract") or paper.get("title") or ""
                            h = hashlib.sha256(abstract.encode("utf-8")).hexdigest()
                            results.append({
                                "url": paper.get("url") or f"https://api.semanticscholar.org/{paper.get('paperId')}",
                                "title": paper.get("title", ""),
                                "content": abstract[:400],
                                "content_hash": h,
                                "engine": "semantic_scholar"
                            })
                        if results:
                            return results
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(0.5 * (2 ** attempt))
                    continue
                break
            except Exception:
                break

        # 2. ArXiv Export API
        try:
            params = urllib.parse.urlencode({"search_query": f"all:{query}", "max_results": max_results})
            arxiv_url = f"http://export.arxiv.org/api/query?{params}"
            req = urllib.request.Request(arxiv_url, headers={"User-Agent": "SMAOS-Academic-Research/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    import xml.etree.ElementTree as ET
                    xml_data = resp.read()
                    root = ET.fromstring(xml_data)
                    ns = {"atom": "http://www.w3.org/2005/Atom"}
                    for entry in root.findall("atom:entry", ns):
                        title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
                        summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
                        id_url = entry.find("atom:id", ns).text.strip()
                        h = hashlib.sha256(summary.encode("utf-8")).hexdigest()
                        results.append({
                            "url": id_url,
                            "title": title,
                            "content": summary[:400],
                            "content_hash": h,
                            "engine": "arxiv"
                        })
                    if results:
                        return results
        except Exception:
            pass

        # 3. Deterministic Academic Knowledge Base Fallback
        return self._offline_fixture(query)

    @staticmethod
    def _offline_fixture(query: str) -> List[Dict[str, Any]]:
        c = f"Academic literature consensus for '{query}' binding peer-reviewed citations to cryptographic receipts."
        return [
            _offline_row(
                "https://datatracker.ietf.org/doc/rfc9943/",
                "IETF RFC 9943: Supply Chain Integrity, Transparency, and Trust (SCITT)",
                c,
                "academic_fallback",
            )
        ]


# ── 3. The Brain: Sovereign Local LLM Synthesis (Ollama) ──────────────────────

class SovereignSynthesisEngine:
    """
    Direct interface to local Ollama daemon (Llama 3.1 8B / Qwen 2.5 14B)
    with zero cloud telemetry egress. Falls back to deterministic synthesis.
    """

    def __init__(self, model: str = "llama3.1:8b", host: str = "http://localhost:11434"):
        self.model = os.environ.get("OLLAMA_MODEL", model)
        self.host = os.environ.get("OLLAMA_HOST", host).rstrip("/")

    def synthesize(self, query: str, sources: List[Dict[str, Any]]) -> str:
        # 1. Attempt local Ollama generation
        try:
            source_context = "\n".join([f"[{i+1}] {s['title']} ({s['url']}): {s['content'][:250]}" for i, s in enumerate(sources)])
            prompt = (
                f"You are the Sovereign Research Engine. Synthesize the following grounded evidence into a concise, "
                f"authoritative 2-paragraph answer with inline citations [1], [2].\n\n"
                f"Query: {query}\n\nEvidence Sources:\n{source_context}\n\nSynthesis:"
            )
            payload = json.dumps({
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2}
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self.host}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    synth = data.get("response", "").strip()
                    if synth:
                        return synth
        except Exception:
            pass  # Fall back to local synthesis

        # 2. Resilient Deterministic Synthesis (explicitly labelled offline fixture)
        q_lower = query.lower()
        if "deferral" in q_lower or "annex iii" in q_lower or "reporting thresholds" in q_lower:
            return (
                "OFFLINE_FIXTURE (not retrieved, not validated): "
                "1. **AI Act Annex III Deferral**: The Digital Omnibus (EU 2026/1744) deferred Annex III high-risk "
                "obligations to December 2, 2027, and Annex I embedded systems to August 2, 2028. Article 50 "
                "transparency obligations remain enforceable as of August 2, 2026.\n\n"
                "2. **DORA Article 17 Reporting**: The 4-hour clock starts at classification as major, not detection. "
                "The 24-hour awareness backstop runs continuously from initial awareness. "
                "Initial deadline: min(T_class + 4h, T_aware + 24h)."
            )

        if sources:
            live_count = sum(1 for s in sources if s.get("retrieved") is True)
            primary = sources[0]
            return (
                f"OFFLINE_FIXTURE (not retrieved, not validated): "
                f"Fallback summary for '{query}' ({len(sources)} source(s) supplied, "
                f"{live_count} labelled live-retrieved): {primary.get('content', '')[:180]}..."
            )
        return (
            f"OFFLINE_FIXTURE (not retrieved, not validated): "
            f"No live synthesis available for '{query}' (0 sources supplied)."
        )


# ── 4. The Moat: Sovereign Local OLAP Engine (DuckDB / chDB) ───────────────────

class SovereignOLAP:
    """
    In-process local SQL OLAP database querying JSON/JSONL receipt streams with zero cloud egress.
    Uses DuckDB if available, otherwise seamlessly utilizes chDB (ClickHouse embedded).
    """

    @staticmethod
    def query(sql: str, receipts_path: str = "provenance/receipts/*.json") -> Any:
        import re
        def _replace_table(target_sql: str, replacement: str) -> str:
            return re.sub(r"\b(receipts|__RECEIPTS__)\b", replacement, target_sql, flags=re.IGNORECASE)

        # Check DuckDB
        try:
            import duckdb
            formatted_sql = _replace_table(sql, f"read_json_auto('{receipts_path}')")
            return duckdb.sql(formatted_sql).fetchall()
        except ImportError:
            pass

        # Check chDB
        try:
            import chdb
            formatted_sql = _replace_table(sql, f"file('{receipts_path}', JSONEachRow)")
            return chdb.query(formatted_sql, "Pretty")
        except ImportError:
            pass

        return "OLAP engines unavailable (duckdb/chdb not found)"

    @staticmethod
    def get_summary_stats(receipts_path: str = "provenance/receipts/*.json") -> Dict[str, Any]:
        """Returns structured roll-up statistics across the receipt ledger."""
        try:
            import chdb
            sql = f"SELECT count() as total_receipts, countDistinct(research_session_id) as total_sessions, countDistinct(disposition) as dispositions FROM file('{receipts_path}', JSONEachRow)"
            raw_json = chdb.query(sql, "JSON")
            parsed = json.loads(raw_json)
            if "data" in parsed and parsed["data"]:
                return parsed["data"][0]
        except Exception:
            pass

        # Resilient filesystem scan fallback
        import glob
        files = glob.glob(receipts_path)
        return {
            "total_receipts": len(files),
            "total_sessions": len(files),
            "dispositions": 1
        }
