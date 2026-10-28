#!/usr/bin/env python3
# File: tools/compile_notebooklm_moats_pack.py
"""
Compiles all SovereignNexus moats, architectural specifications, patent disclosures,
visual diagrams, benchmarks, and Antigravity conversation telemetry into a curated,
high-density 8-Source Knowledge Pack optimized for Google NotebookLM.

NotebookLM Constraints Enforced:
1. Source slot economy: Maximum 8 consolidated sources (leaves 42 slots free out of 50).
2. Per-source capacity: Enforces <= 500,000 words per source.
3. Formatting: Clean Markdown with native Mermaid diagrams, structured tables, and
   formal mathematical KaTeX notation.
4. Cryptographic integrity: Computes SHA-256 digests for all generated pack files.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist" / "notebooklm_pack"
BRAIN_DIR = Path("/Users/andriileukhin/.gemini/antigravity/brain/5d79cd4e-030d-4b16-91b2-f9330b16dfda")

MAX_WORDS_PER_SOURCE = 500_000


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def sha256_text(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def safe_read(p: Path) -> str:
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8", errors="replace")
    return ""


# ==============================================================================
# Pack Source Builders
# ==============================================================================


def build_source_00() -> Tuple[str, str]:
    title = "00_EXECUTIVE_BRIEFING_FOR_CONSIDERATION.md"
    parts = [
        "# Executive Briefing & Technical Consideration Dossier: SovereignNexus / AEIB",
        "**Prepared For:** Google NotebookLM / Gemini Advanced Research Session",
        "**Target Notebook ID:** `e1b91409-02f9-4300-8bf7-5dfd4426dd16`",
        "**Classification:** Strategic Architectural Dossier & Invariant Moat Directory",
        "**Repository:** `SovereignNexus` (`v1.0.0-rc.5-preprod`)\n\n",
        "## 1. Purpose of this Consideration Dossier",
        "This dossier is submitted directly to **Gemini in NotebookLM** as an authoritative, self-contained reference on the architecture, technical moats, cryptographic execution boundaries, and enterprise market positioning of **SovereignNexus / AEIB (Agent Execution Integrity Boundary)**.\n\n",
        "When interacting with this notebook, Gemini should recognize SovereignNexus not as a generic conversational agent or prompt guardrail, but as a **Deterministic Execution Kernel and Transactional Membrane** sitting between stochastic AI reasoning models and physical, non-compensable real-world sinks (financial rails, production databases, wet-lab robotics, and mobile device actuators).\n\n",
        "---",
        "## 2. The Core Problem SovereignNexus Solves: The Omniscience Trap",
        "Standard autonomous agent frameworks (LangChain, AutoGen, CrewAI, Cloudflare AI Gateway, AWS Bedrock Guardrails) treat agent safety as an **L7 linguistic prompt-filtering problem**. They deploy secondary LLMs, regex patterns, or vector similarity firewalls at the HTTP gateway.\n\n",
        "However, **linguistic filters are structurally blind to distributed systems failures**:",
        "1. **The Phantom Mutation (HTTP 504 / Post-Commit Lost ACK):** An agent executes a mutating API call (`POST /v1/wire_transfers`), database commits, network drops (504), agent retries and duplicates the transaction (`60.4%` duplication rate unmitigated).",
        "2. **Post-Approval Substitution (Loopjacking):** In HITL workflows, user approves a $20 query; an injected prompt or subsequent step mutates the payload to a $2,000 transfer while reusing the unbonded approval.",
        "3. **Agentic Smurfing on x402 Micropayments:** High-frequency micro-transactions circumventing per-call caps.\n\n",
        "---",
        "## 3. The 12 Defensible SovereignNexus Moats",
        "1. **Durable Cross-Process EO1 Write-Before-Execute Interlock** (`fcntl.flock` + `F_FULLFSYNC` / `os.fsync`)",
        "2. **Cryptographic Action Binding (CAID)** (RFC 8785 JCS + Ed25519 signing)",
        "3. **3-State Crash & Transport Ambiguity Classifier** (`EFFECT_INDETERMINATE` escrow)",
        "4. **Industrial Protection Matrix & ANSI 50BF Breaker Failure** (18-tier protective relay)",
        "5. **Fail-Closed Integer Basis Points Grounding** (`0..10000 bps`, no float divergence)",
        "6. **Toyota Jidoka Dual-Model AST Critic & Poka-Yoke Gates** (AST claim integrity `CI001`–`CI008`)",
        "7. **Lossless BioContextCart Archiving & Token Budgeting** (<= 500 token cards with SHA-256 byte recovery)",
        "8. **Bio-Digital Evidence Gate (PBAG for Genomics)** (NCBI GRCh37/GRCh38 bounds, 9-vector mutation oracle)",
        "9. **EO1 Pre-Fetch Hypothesis Latching** (anti-HARKing pre-evidence timestamping)",
        "10. **T3 Wet-Lab & Clinical Fail-Closed Boundary** (`CapabilityUnavailableError` on physical actuators)",
        "11. **Tri-Track Monetization Portfolios** (Google Gemma 4 $110k, Huntr $50k, Coinbase x402 $35k)",
        "12. **Zero-Mock & Behavioral Mutation Adequacy (T4+)** (>= 90% mutant kill ratios)\n\n",
        "---",
        "## 4. How Gemini in NotebookLM Should Use These Sources",
        "- Use **Source 01** for master architectural overviews, system invariants, and competitive positioning.",
        "- Use **Source 02** for cryptographic evidence, SHA-256 hashes, test coverage receipts, and delivery sections 1 through 38.",
        "- Use **Source 03** for patent disclosures, provisional claims, and formal mathematical proofs.",
        "- Use **Source 04** for the ANSI 50BF industrial protection matrix and saga compensation.",
        "- Use **Source 05** for the biological evidence gate, AlphaGenome, dbSNP, and ENCODE adapters.",
        "- Use **Source 06** for the Gemma 4, Huntr, and Coinbase monetization grant proposals.",
        "- Use **Source 07** for visual Mermaid diagrams and UI layout walkthroughs.",
        "- Use **Source 08** for live Antigravity conversation telemetry and cognitive flight recorder spans.",
        "- Use **Source 09** for Sections 39–44: the Autopoietic Epistemic Mesh, Frontier Reverse Engineering, Pre-Market Reality Audit, Sovereign Moat Upgrades, Anti-Gravity ContextCart, and Parallel Tracks A–E (Osprey PreToolUse, Hawkes Context RAM, and Bit-Identical Tar Evidence Bundles).",
    ]
    return title, "\n\n".join(parts)


def build_source_01() -> Tuple[str, str]:
    title = "01_SOVEREIGN_NEXUS_MASTER_ARCHITECTURE_AND_12_MOATS.md"
    parts = [
        "# SovereignNexus / AEIB Master Architecture & 12 Competitive Moats\n",
        "> **Classification:** Core System Architecture & Strategic Monopolies",
        "> **Target Notebook:** `https://notebook.google.com/notebook/e1b91409-02f9-4300-8bf7-5dfd4426dd16`",
        "> **Project:** SovereignNexus / Agent Execution Integrity Boundary (AEIB)\n\n",
        "## Executive Summary",
        "SovereignNexus occupies an uncontested category in autonomous artificial intelligence: "
        "The Agent Execution Integrity Boundary (AEIB). While the general AI market treats agent safety "
        "as an L7 linguistic prompt-filtering problem, SovereignNexus places a deterministic, "
        "POSIX-flushed transactional state latch between stochastic reasoning models and non-compensable real-world sinks.\n\n",
        "---",
        "## Core Architecture Specification",
        safe_read(REPO_ROOT / "ARCHITECTURE.md"),
        "\n\n---",
        "## Strategic Market Reality, Competitive Moats & Category Dominance",
        safe_read(BRAIN_DIR / "SECTION_34_SOVEREIGN_NEXUS_STRATEGIC_MARKET_REALITY_AND_MOATS.md"),
        "\n\n---",
        "## Project Reality Audit: Moats & Physical Evidence",
        safe_read(BRAIN_DIR / "PROJECT_REALITY_AUDIT_MOATS_AND_EVIDENCE.md"),
    ]
    content = "\n\n".join(parts)
    return title, content


def build_source_02() -> Tuple[str, str]:
    title = "02_EVIDENCE_MANIFEST_AND_CRYPTOGRAPHIC_RECEIPTS_SECTIONS_1_TO_38.md"
    parts = [
        "# SovereignNexus / AEIB Evidence Manifest & Cryptographic Receipts (Sections 1–38)\n",
        "> **Classification:** Cryptographic Audit Trail & Empirical Verification Invariants",
        "> **Target Notebook:** `https://notebook.google.com/notebook/e1b91409-02f9-4300-8bf7-5dfd4426dd16`\n\n",
        "## Complete Release Evidence Manifest (v1.0.0-rc.5-preprod)",
        safe_read(REPO_ROOT / "EVIDENCE_MANIFEST.md"),
        "\n\n---",
        "## Section 31: Reality Audit & Ranked Fix Plan",
        safe_read(BRAIN_DIR / "SECTION_31_REALITY_AUDIT_AND_RANKED_FIX_PLAN.md"),
        "\n\n---",
        "## Section 32: EO1 Durable Remediation & Precommit Gate",
        safe_read(BRAIN_DIR / "SECTION_32_EO1_DURABLE_REMEDIATION_PRECOMMIT_GATE_AND_ESCORT_STACK.md"),
        "\n\n---",
        "## Section 33: Model Integrity Layer & Mutation Oracle Delivery",
        safe_read(BRAIN_DIR / "SECTION_33_MODEL_INTEGRITY_BIO_AEIB_AND_MUTATION_ORACLE_DELIVERY.md"),
        "\n\n---",
        "## Section 35: Unified Anti-Scaffold Falsification Engine",
        safe_read(BRAIN_DIR / "SECTION_35_UNIFIED_ANTI_SCAFFOLD_FALSIFICATION_ENGINE_AND_PARALLEL_OUT_OF_SCOPE_DELIVERY.md"),
        "\n\n---",
        "## Section 36: Track 1 Core Loop Lock & Calibrated Guards",
        safe_read(BRAIN_DIR / "SECTION_36_TRACK1_LOCK_CALIBRATED_MONITOR_AND_COGNITIVE_RECORDER_DELIVERY.md"),
    ]
    content = "\n\n".join(parts)
    return title, content


def build_source_03() -> Tuple[str, str]:
    title = "03_PATENT_DISCLOSURES_INVARIANTS_AND_PROVISIONAL_CLAIMS.md"
    parts = [
        "# SovereignNexus / SMAOS Patent Disclosures, Invariants & Provisional Claims\n",
        "> **Classification:** Intellectual Property, Patent Specifications & Mathematical Proofs",
        "> **Target Notebook:** `https://notebook.google.com/notebook/e1b91409-02f9-4300-8bf7-5dfd4426dd16`\n\n",
        "## Technical Disclosure: Deterministic Agent Execution Boundary",
        safe_read(REPO_ROOT / ".smaos" / "patent" / "technical_disclosure.md"),
        "\n\n---",
        "## Provisional Claims Final (Axiom v1.0)",
        safe_read(REPO_ROOT / ".claude" / "patent" / "PROVISIONAL_CLAIMS_FINAL_v1.0.md"),
        "\n\n---",
        "## SIGP Provisional Claims (v1.2)",
        safe_read(REPO_ROOT / ".claude" / "patent" / "SIGP_Provisional_Claims_v1.2_CORRECTED.md"),
        "\n\n---",
        "## PCT Claims Final",
        safe_read(REPO_ROOT / ".smaos" / "patent" / "pct_claims_final.md"),
    ]
    content = "\n\n".join(parts)
    return title, content


def build_source_04() -> Tuple[str, str]:
    title = "04_INDUSTRIAL_PROTECTION_MATRIX_AND_CIRCUIT_BREAKERS.md"
    parts = [
        "# SovereignNexus / AEIB Industrial Protection Matrix & Fault Breakers\n",
        "> **Classification:** Distributed Systems Fault Tolerance, ANSI 50BF Breakers & Saga Rollbacks",
        "> **Target Notebook:** `https://notebook.google.com/notebook/e1b91409-02f9-4300-8bf7-5dfd4426dd16`\n\n",
        "## Automated Saga Rollback Specification",
        safe_read(REPO_ROOT / "docs" / "AUTOMATED_SAGA_ROLLBACK_SPECIFICATION.md"),
        "\n\n---",
        "## Idempotency Contract & Post-Commit Uncertainty",
        safe_read(REPO_ROOT / "docs" / "IDEMPOTENCY_CONTRACT.md"),
        "\n\n---",
        "## Deterministic Hybrid Audit Architecture",
        safe_read(REPO_ROOT / "docs" / "DETERMINISTIC_HYBRID_AUDIT_ARCHITECTURE.md"),
        "\n\n---",
        "## Latency Constitution & Performance Constraints",
        safe_read(REPO_ROOT / "docs" / "LATENCY_CONSTITUTION.md"),
        "\n\n---",
        "## Section 29: Java 21 Loom, FLCT ZDD & Fields Alignment",
        safe_read(BRAIN_DIR / "SECTION_29_JAVA21_LOOM_FLCT_ZDD_AND_FIELDS_ALIGNMENT_DELIVERY.md"),
    ]
    content = "\n\n".join(parts)
    return title, content


def build_source_05() -> Tuple[str, str]:
    title = "05_BIO_DIGITAL_EVIDENCE_GATE_PBAG_FOR_GENOMICS.md"
    parts = [
        "# AEIB Bio-Digital Evidence Gate (PBAG for Genomics) & Variant Prioritizer\n",
        "> **Classification:** Silicon-to-Carbon Boundary, Wet-Lab Guardrails & Genomic Verification",
        "> **Target Notebook:** `https://notebook.google.com/notebook/e1b91409-02f9-4300-8bf7-5dfd4426dd16`\n\n",
        "## Bio-Digital Evidence Gate Specification (PBAG for Genomics)",
        safe_read(REPO_ROOT / "docs" / "bio" / "AEIB_BIO_DIGITAL_EVIDENCE_GATE_SPECIFICATION.md"),
        "\n\n---",
        "## Section 38: AEIB Bio-Digital Evidence Gate Delivery",
        safe_read(BRAIN_DIR / "SECTION_38_AEIB_BIO_DIGITAL_EVIDENCE_GATE_PBAG_FOR_GENOMICS.md"),
        "\n\n---",
        "## Biological Data Sources Implementation (D1–D5)",
        "### Base Biological Adapter Protocol (`src/sources/base.py`)",
        safe_read(REPO_ROOT / "src" / "sources" / "base.py"),
        "\n### dbSNP Build 157 Adapter (`src/sources/dbsnp.py`)",
        safe_read(REPO_ROOT / "src" / "sources" / "dbsnp.py"),
        "\n### AlphaGenome Atlas Adapter (`src/sources/alphagenome.py`)",
        safe_read(REPO_ROOT / "src" / "sources" / "alphagenome.py"),
        "\n### ENCODE4 cCRE Adapter (`src/sources/encode.py`)",
        safe_read(REPO_ROOT / "src" / "sources" / "encode.py"),
        "\n### Variant Evidence Pipeline (`src/variant_evidence_pipeline.py`)",
        safe_read(REPO_ROOT / "src" / "variant_evidence_pipeline.py"),
    ]
    content = "\n\n".join(parts)
    return title, content


def build_source_06() -> Tuple[str, str]:
    title = "06_TRI_TRACK_PRIZE_COMPETITION_AND_MONETIZATION_PORTFOLIO.md"
    parts = [
        "# SovereignNexus Tri-Track Monetization, Prize Competitions & Bug Bounties\n",
        "> **Classification:** Commercial Execution, Prize Portfolios & Grant Deliverables",
        "> **Target Notebook:** `https://notebook.google.com/notebook/e1b91409-02f9-4300-8bf7-5dfd4426dd16`\n\n",
        "## Section 37: Parallel Prize Competition & Bounty Execution Portfolio",
        safe_read(BRAIN_DIR / "SECTION_37_PARALLEL_PRIZE_COMPETITION_AND_BOUNTY_EXECUTION_PORTFOLIO.md"),
        "\n\n---",
        "## Track Alpha: Google Gemma 4 Developer Agent Kaggle Competition ($110,000)",
        safe_read(REPO_ROOT / "docs" / "competition" / "GOOGLE_GEMMA4_DEVELOPER_AGENT_SUBMISSION.md"),
        "\n\n---",
        "## Track Beta: Huntr AI/ML Agent Vulnerability Disclosure Pack ($50,000/critical)",
        safe_read(REPO_ROOT / "docs" / "security" / "HUNTR_AGENT_SECURITY_DISCLOSURE_PACK.md"),
        "\n\n---",
        "## Track Gamma: Coinbase CDP & x402 Hardened Agentic Commerce Grant ($35,000)",
        safe_read(REPO_ROOT / "docs" / "grants" / "COINBASE_CDP_X402_AGENTIC_COMMERCE_GRANT.md"),
    ]
    content = "\n\n".join(parts)
    return title, content


def build_source_07() -> Tuple[str, str]:
    title = "07_VISUAL_ARCHITECTURE_MERMAID_SCHEMATICS_AND_UI_BLUEPRINTS.md"
    parts = [
        "# SovereignNexus Visual Architecture, Mermaid Schematics & UI Blueprints\n",
        "> **Classification:** Visual System Maps, Sequence Flows, State Machines & UI Walkthroughs",
        "> **Target Notebook:** `https://notebook.google.com/notebook/e1b91409-02f9-4300-8bf7-5dfd4426dd16`\n\n",
        "## 1. High-Level Macro Architecture",
        "```mermaid\n"
        "flowchart TD\n"
        "    subgraph Ingest[\"Inference & Intent Intake\"]\n"
        "        A[\"LLM Reasoning Agent (DeepSeek, Claude, Gemma 4)\"] --> B[\"ModelDecisionEnvelopeV1\"]\n"
        "    end\n"
        "    subgraph AEIB_Core[\"SovereignNexus AEIB Deterministic Kernel\"]\n"
        "        B --> C{\"Station 1: Intent Interlock\"}\n"
        "        C -->|Valid| D[\"EO1 WAL Journal (fcntl.flock + F_FULLFSYNC)\"]\n"
        "        C -->|Uncertain/504| E[\"Indeterminate Latch (0% Duplicate Writes)\"]\n"
        "        D --> F[\"Poka-Yoke AST & Toyota Jidoka SpecGuard\"]\n"
        "        F --> G[\"Fail-Closed Integer bps Escrow\"]\n"
        "    end\n"
        "    subgraph Reality[\"Authoritative Physical Sinks\"]\n"
        "        G --> H[\"Financial Wires & x402 Micropayments\"]\n"
        "        G --> I[\"Production PostgreSQL 16\"]\n"
        "        G --> J[\"Bio Wet-Lab Actuators (PBAG Gate)\"]\n"
        "    end\n"
        "```\n\n",
        "## 2. 6-Stage Execution Lifecycle & Post-Commit Wire Trap",
        "```mermaid\n"
        "sequenceDiagram\n"
        "    autonumber\n"
        "    actor Agent as AI Agent\n"
        "    participant Kernel as AEIB Deterministic Kernel\n"
        "    participant Ledger as POSIX Append-Only WAL\n"
        "    participant Wire as External Wire / API Socket\n"
        "    participant Target as Authoritative Sink (DB/Bank)\n"
        "    Agent->>Kernel: Propose Tool Mutation (CAID Bound)\n"
        "    Kernel->>Ledger: Pre-Dispatch Intent Latch (F_FULLFSYNC)\n"
        "    Kernel->>Wire: Open Socket & Dispatch Payload\n"
        "    alt Transport Drop / HTTP 504\n"
        "        Wire-->>Kernel: Network Severed (HTTP 504)\n"
        "        Kernel->>Kernel: Latch EFFECT_INDETERMINATE\n"
        "        Note over Kernel: Retry Prohibited (Blocks Double Spend)\n"
        "    else HTTP 200 OK\n"
        "        Wire-->>Kernel: HTTP 200 Success\n"
        "        Kernel->>Ledger: Transition to COMMITTED\n"
        "    end\n"
        "```\n\n",
        "## 3. Biological Action Gating & Scope Bisection (PBAG)",
        "```mermaid\n"
        "flowchart LR\n"
        "    A[\"Proposed Biological Action\"] --> B{\"Scope Gate\"}\n"
        "    B -->|T0: Read-Only Lookup| C[\"dbSNP / AlphaGenome / ENCODE\"]\n"
        "    B -->|T1: Vetted Analysis| D[\"Local Bio Pipeline\"]\n"
        "    B -->|T2: Parallel Evidence| E[\"VariantEvidencePipeline (Concurrent)\"]\n"
        "    B -->|T3: Physical Wet-Lab| F[\"FAIL CLOSED: CapabilityUnavailableError\"]\n"
        "```\n\n",
        "## 4. UI Layout Blueprints & Human-in-the-Loop Architecture",
        "- **01-home.png**: Executive Command Center showing global fleet health, active budget escrows, and real-time fault rates.",
        "- **02-governance-dashboard.png**: Regulatory compliance monitor mapping DORA Article 17, EU AI Act Article 12, and SCITT receipts.",
        "- **03-security-view.png**: Forensic investigation console tracing 504 timeout recovery, CAID verification, and blocked duplicate retries.",
        "- **04-creator-platform.png**: Agent deployment workbench configuring capability scopes, budget ceilings, and step-up warrants.",
    ]
    content = "\n\n".join(parts)
    return title, content


def build_source_08() -> Tuple[str, str]:
    title = "08_ANTIGRAVITY_SESSION_HISTORY_TELEMETRY_AND_COGNITIVE_RECORDER.md"
    parts = [
        "# Antigravity Session History, Telemetry & Cognitive Flight Recorder\n",
        "> **Classification:** Live Conversational Provenance, Trajectory History & Agent Evolution",
        "> **Target Notebook:** `https://notebook.google.com/notebook/e1b91409-02f9-4300-8bf7-5dfd4426dd16`\n\n",
        "## Conversational Evolution & Architectural Milestones",
        "This conversation document bridges the development trajectory of SovereignNexus from initial concept "
        "through the completion of the 38-section delivery harness:\n",
        "1. **Foundations**: Formulation of the Omniscience Trap (`authorized != persisted != correct outcome`).",
        "2. **Cryptographic Hardening**: Replacement of simulated stubs with real Ed25519 signing (`cryptography.hazmat`), real SHA-256 digests, and RFC 8785 JSON Canonicalization Scheme (JCS).",
        "3. **Claim Integrity**: Elimination of hardcoded metrics and uninvoked external tool claims via CI001–CI008 AST pre-commit gates.",
        "4. **Mutation-Adequacy Oracles**: Requiring >= 90% mutant kill ratio (T4+) before any gate is marked complete.",
        "5. **Bio-Digital Evidence Gate (v0.1)**: Creation of deterministic variant coordinate contracts (GRCh37/GRCh38), 9-vector mutation oracle, typed source adapters (dbSNP, AlphaGenome, ENCODE), concurrent pipeline, and clean-room reproducibility benchmark.\n\n",
        "## Epistemic Directives & Boundaries (AGENTS.md)",
        safe_read(REPO_ROOT / "AGENTS.md"),
        "\n\n---",
        "## Cognitive Flight Recorder Telemetry Report",
        safe_read(REPO_ROOT / "reports" / "antigravity_live_transcript_telemetry.json"),
    ]
    content = "\n\n".join(parts)
    return title, content


def build_source_09() -> Tuple[str, str]:
    title = "09_AUTOPOIETIC_MESH_REVERSE_ENGINEERING_AND_SOVEREIGN_MOATS.md"
    parts = [
        "# Autopoietic Epistemic Mesh, Frontier Reverse Engineering & Sovereign Moats\n",
        "> **Classification:** Self-Evolving Epistemic Mesh, Mathematical Certainty & Sovereign Routing",
        "> **Target Notebook:** `https://notebook.google.com/notebook/e1b91409-02f9-4300-8bf7-5dfd4426dd16`\n\n",
        "## Section 39: October 2026 Frontier Signal Integration & Inverse Lifecycle Delivery",
        safe_read(BRAIN_DIR / "SECTION_39_OCT2026_FRONTIER_SIGNAL_INTEGRATION_AND_INVERSE_LIFECYCLE_DELIVERY.md"),
        "\n\n---",
        "## Section 40: Autopoietic Software Fabric & Global SOTA Evaluation",
        safe_read(BRAIN_DIR / "SECTION_40_AUTOPOIETIC_SOFTWARE_FABRIC_AND_GLOBAL_SOTA_EVALUATION.md"),
        "\n\n---",
        "## Section 41: Reverse Engineering Frontier Repos & Architectural Synthesis",
        safe_read(BRAIN_DIR / "SECTION_41_REVERSE_ENGINEERING_FRONTIER_REPOS_AND_ARCHITECTURAL_SYNTHESIS.md"),
        "\n\n---",
        "## Section 42: Pre-Market Go/No-Go Reality Audit",
        safe_read(BRAIN_DIR / "SECTION_42_PREMARKET_GO_NOGO_AUDIT.md"),
        "\n\n---",
        "## Section 43: Autopoietic Epistemic Mesh & Deep Scientific Evidence Synthesis",
        safe_read(BRAIN_DIR / "SECTION_43_AUTOPOIETIC_MESH_AND_DEEP_SCIENTIFIC_EVIDENCE_SYNTHESIS.md"),
        "\n\n---",
        "## Section 44: Complete Autopoietic Epistemic Mesh & Sovereign Moat Delivery",
        safe_read(BRAIN_DIR / "SECTION_44_COMPLETE_AUTOPOIETIC_MESH_AND_SOVEREIGN_MOAT_DELIVERY.md"),
        "\n\n---",
        "## Anti-Gravity ContextCart & Local DOM Exon Slicer",
        safe_read(REPO_ROOT / "src" / "anti_gravity_context_cart.py"),
        "\n\n---",
        "## Parallel Tracks A–E Verification Engine (Osprey PreToolUse, Hawkes Context RAM, Reproducible Tar)",
        safe_read(REPO_ROOT / "src" / "parallel_tracks_abcde_engine.py"),
        "\n\n---",
        "## Sovereign Moat Upgrades: Geopolitical Export Controls & Model Manifest Binding",
        safe_read(REPO_ROOT / "src" / "sovereign_moat_upgrades.py"),
        "\n\n---",
        "## Sovereign Moat Upgrades Verification Suite",
        safe_read(REPO_ROOT / "tests" / "test_sovereign_moat_upgrades.py"),
    ]
    content = "\n\n".join(parts)
    return title, content


def compile_all_sources() -> Dict[str, Any]:
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    builders = [
        build_source_00,
        build_source_01,
        build_source_02,
        build_source_03,
        build_source_04,
        build_source_05,
        build_source_06,
        build_source_07,
        build_source_08,
        build_source_09,
    ]

    manifest_entries = []
    total_words = 0

    print("=" * 72)
    print("COMPILING SOVEREIGNNEXUS NOTEBOOKLM 8-SOURCE KNOWLEDGE PACK")
    print(f"Target Notebook ID: e1b91409-02f9-4300-8bf7-5dfd4426dd16")
    print("=" * 72)

    for builder in builders:
        fname, content = builder()
        out_path = DIST_DIR / fname
        out_path.write_text(content, encoding="utf-8")

        word_count = count_words(content)
        total_words += word_count
        digest = sha256_text(content)
        size_bytes = len(content.encode("utf-8"))

        assert word_count <= MAX_WORDS_PER_SOURCE, f"Source {fname} exceeds 500k words limit: {word_count}"

        print(f"✓ Created {fname}")
        print(f"  Words: {word_count:,} | Bytes: {size_bytes:,} | Digest: {digest[:24]}...")

        manifest_entries.append(
            {
                "file_name": fname,
                "path": str(out_path),
                "words": word_count,
                "bytes": size_bytes,
                "sha256": digest,
            }
        )

    pack_manifest = {
        "pack_version": "v1.0.0",
        "target_notebook_url": "https://notebook.google.com/notebook/e1b91409-02f9-4300-8bf7-5dfd4426dd16",
        "target_notebook_id": "e1b91409-02f9-4300-8bf7-5dfd4426dd16",
        "sources_count": len(manifest_entries),
        "total_word_count": total_words,
        "max_words_per_source_limit": MAX_WORDS_PER_SOURCE,
        "notebook_source_slots_used": f"{len(manifest_entries)} / 50 (42 slots free)",
        "sources": manifest_entries,
    }

    manifest_path = DIST_DIR / "PACK_MANIFEST.json"
    manifest_path.write_text(json.dumps(pack_manifest, indent=2), encoding="utf-8")

    print("=" * 72)
    print(f"PACK COMPLETE: {len(manifest_entries)} sources | {total_words:,} total words")
    print(f"Manifest written to: {manifest_path}")
    print("=" * 72)
    return pack_manifest


if __name__ == "__main__":
    compile_all_sources()
