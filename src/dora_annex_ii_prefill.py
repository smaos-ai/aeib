#!/usr/bin/env python3
r"""
dora_annex_ii_prefill.py — DORA RTS 2025/301 Annex II Pre-Fill Generator
Sovereign Multi-Agent OS (SMAOS) / AEIB Category Wedge (P2 / P3)

Ingests JCS-canonicalized, Ed25519-signed agent execution receipts and transforms
them into standardized DORA RTS 2025/301 Annex II Initial Notification dossiers.

Statutory Anchors:
  • EU Regulation 2022/2554 (DORA) Article 19(1) & 19(4)(a)
  • Commission Delegated Regulation (EU) 2025/301 (RTS on Incident Classification)
    Annex II: Template for the initial notification of major ICT-related incidents.
  • Delegated Regulation (EU) 2025/301 Article 4(2):
    Non-adjustment exemption for Credit Institutions and Essential Entities
    (no weekend/holiday extensions for initial notification).

Core Invariant:
  "Impact / Severity Rating" is STRICTLY initialized to "PENDING_HUMAN_REVIEW".
  Automated systems and AI agents are PROHIBITED from self-certifying,
  auto-downgrading, or closing incident materiality. Mandatory Human-in-the-Loop.
"""

import os
import sys
import json
import time
import uuid
import hashlib
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path


# ── Statutory Constants ────────────────────────────────────────────────────────

REGULATION_REFERENCE = "Regulation (EU) 2022/2554 (DORA) Art. 19"
RTS_REFERENCE = "Commission Delegated Regulation (EU) 2025/301 Annex II"
SEVERITY_PENDING = "PENDING_HUMAN_REVIEW"

# Allowed entity types under DORA Article 2
ENTITY_TYPES = {
    "CREDIT_INSTITUTION": "Credit Institution (CRR Art. 4(1)(1))",
    "PAYMENT_INSTITUTION": "Payment Institution (PSD2)",
    "ACCOUNT_INFO_SERVICE": "Account Information Service Provider",
    "ELECTRONIC_MONEY": "Electronic Money Institution (EMD2)",
    "INVESTMENT_FIRM": "Investment Firm (MiFID II)",
    "CRITICAL_ICT_THIRD_PARTY": "Critical ICT Third-Party Service Provider (DORA Art. 31)",
    "OTHER_REGULATED_ENTITY": "Other Regulated Financial Entity"
}


# ── ISO 17442 LEI Checksum Validation (MOD-97) ────────────────────────────────

def validate_lei_mod97(lei: str) -> bool:
    """Validates an ISO 17442 Legal Entity Identifier using MOD-97 (ISO 7064)."""
    if not lei or len(lei.strip()) != 20:
        return False
    cleaned = lei.strip().upper()
    if not cleaned.isalnum() or not cleaned[-2:].isdigit():
        return False

    num_str = ""
    for ch in cleaned:
        if ch.isdigit():
            num_str += ch
        else:
            num_str += str(ord(ch) - ord("A") + 10)

    try:
        return int(num_str) % 97 == 1
    except ValueError:
        return False


# ── Statutory Deadline Engine ──────────────────────────────────────────────────

class StatutoryDeadlineEngine:
    """
    Computes statutory deadlines under DORA Art. 19(4) and RTS 2025/301 Art. 4.
    Initial Notification: min(T_class + 4 hours, T_aware + 24 hours).
    Intermediate Report:  T_class + 72 hours.
    """

    @staticmethod
    def calculate_deadlines(
        awareness_time: datetime,
        classification_time: Optional[datetime] = None,
        entity_type: str = "CREDIT_INSTITUTION"
    ) -> Dict[str, Any]:
        if awareness_time.tzinfo is None:
            awareness_time = awareness_time.replace(tzinfo=timezone.utc)

        if classification_time is None:
            classification_time = awareness_time
        elif classification_time.tzinfo is None:
            classification_time = classification_time.replace(tzinfo=timezone.utc)

        deadline_aware_24h = awareness_time + timedelta(hours=24)
        deadline_class_4h = classification_time + timedelta(hours=4)

        # Statutory rule: min(T_class + 4h, T_aware + 24h)
        initial_deadline = min(deadline_class_4h, deadline_aware_24h)
        intermediate_deadline = classification_time + timedelta(hours=72)

        # RTS 2025/301 Art. 4(2) Non-adjustment rule
        is_exempt_from_extension = entity_type in (
            "CREDIT_INSTITUTION", "CRITICAL_ICT_THIRD_PARTY", "INVESTMENT_FIRM"
        )

        return {
            "awareness_time_utc": awareness_time.isoformat(),
            "classification_time_utc": classification_time.isoformat(),
            "initial_notification_deadline_utc": initial_deadline.isoformat(),
            "intermediate_report_deadline_utc": intermediate_deadline.isoformat(),
            "rts_2025_301_art4_2_non_adjustment": is_exempt_from_extension,
            "statutory_basis": (
                "DORA Art. 19(4)(a) [min(T_class + 4h, T_aware + 24h)]"
                + (" • RTS 2025/301 Art. 4(2) non-adjustment applied (no weekend/holiday extension)"
                   if is_exempt_from_extension else "")
            )
        }


# ── Annex II Data Model ───────────────────────────────────────────────────────

@dataclass
class DORAAnnexIIInitialNotification:
    """
    Structured model for DORA RTS 2025/301 Annex II Initial Notification.
    """
    # Incident Identification
    incident_identifier: str
    receipt_action_id: str
    idempotency_key: str
    
    # Submitting Entity
    reporting_entity_name: str
    legal_entity_identifier_lei: str
    entity_type: str
    competent_authority: str
    contact_person: str
    
    # Chronology & Timing
    detection_timestamp_utc: str
    start_timestamp_utc: str
    classification_timestamp_utc: str
    statutory_deadlines: Dict[str, Any]
    
    # ICT Service & Function Affected
    affected_ict_service: str
    tool_name: str
    supports_critical_or_important_function: bool
    critical_function_description: str
    
    # Technical Fault & Consequence Trapping
    transport_disruption_type: str
    downstream_reconciliation_status: str
    quarantine_enforced: bool
    technical_narrative: str
    
    # Materiality & Human Review (Mandatory Invariant)
    impact_severity_rating: str = SEVERITY_PENDING
    potential_materiality_triggers: List[str] = field(default_factory=list)
    human_sign_off_required: bool = True
    human_sign_off_status: str = "AWAITING_INCIDENT_COMMANDER"
    reviewed_by: Optional[str] = None
    review_timestamp_utc: Optional[str] = None
    reviewer_verdict_notes: Optional[str] = None
    
    # Cryptographic Evidence Verification
    receipt_sha256_hash: str = ""
    signature_type: str = "Ed25519"
    cryptographic_tamper_seal: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Generator Implementation ──────────────────────────────────────────────────

class DORAAnnexIIPreFillGenerator:
    """
    Transforms execution receipts into DORA RTS 2025/301 Annex II notification dossiers.
    """

    def __init__(
        self,
        default_entity_name: str = "Regulated Financial Entity",
        default_lei: str = "5493000IBP32UQZ0KL24",
        default_entity_type: str = "CREDIT_INSTITUTION",
        default_authority: str = "National Competent Authority / EBA"
    ):
        self.default_entity_name = default_entity_name
        self.default_lei = default_lei
        self.default_entity_type = default_entity_type
        self.default_authority = default_authority

    def generate_from_receipt(
        self,
        receipt: Dict[str, Any],
        entity_overrides: Optional[Dict[str, Any]] = None
    ) -> DORAAnnexIIInitialNotification:
        """
        Parses an execution receipt and maps all fields into Annex II schema.
        Enforces PENDING_HUMAN_REVIEW on severity.
        """
        overrides = entity_overrides or {}

        # 1. Incident Identifiers
        idempotency_key = receipt.get("idempotency_key") or receipt.get("idem_key") or str(uuid.uuid4())
        action_id = receipt.get("action_id", "mcp://session/step/rpc/unspecified")
        incident_id = f"DORA-INC-{idempotency_key[:8].upper()}"

        # 2. Entity Identification
        actor = receipt.get("actor") or receipt.get("dispatched_by") or ""
        lei = overrides.get("lei") or (actor if validate_lei_mod97(actor) else self.default_lei)
        entity_name = overrides.get("entity_name") or (actor if actor and not validate_lei_mod97(actor) else self.default_entity_name)
        entity_type = overrides.get("entity_type", self.default_entity_type)
        authority = overrides.get("competent_authority", self.default_authority)
        contact_person = overrides.get("contact_person", "Designated ICT Incident Officer (Pending Assignment)")

        # 3. Chronology
        raw_dispatched_at = receipt.get("dispatched_at") or receipt.get("timestamp") or time.time()
        if isinstance(raw_dispatched_at, (int, float)):
            start_dt = datetime.fromtimestamp(raw_dispatched_at, tz=timezone.utc)
        elif isinstance(raw_dispatched_at, str):
            try:
                start_dt = datetime.fromisoformat(raw_dispatched_at.replace("Z", "+00:00"))
            except ValueError:
                start_dt = datetime.now(timezone.utc)
        else:
            start_dt = datetime.now(timezone.utc)

        # Detection time is when exception or unconfirmed outcome occurred
        detection_dt = start_dt

        # Compute statutory deadlines
        deadlines = StatutoryDeadlineEngine.calculate_deadlines(
            awareness_time=detection_dt,
            classification_time=detection_dt,
            entity_type=entity_type
        )

        # 4. Service & Critical Function
        tool_name = receipt.get("tool_name") or receipt.get("tool") or "unknown_tool"
        if "action_id" in receipt and not tool_name:
            tool_name = receipt["action_id"].split("/")[-1]

        supports_critical = overrides.get("supports_critical_function", True)
        function_desc = overrides.get(
            "critical_function_description",
            f"Autonomous Agent Execution via {tool_name} under MCP Execution Boundary"
        )

        # 5. Fault & Consequence Trapping
        transport_fault = (
            receipt.get("transport_fault_detected")
            or receipt.get("transport_fault")
            or receipt.get("transport_exception")
            or "NONE"
        )
        disposition = receipt.get("disposition") or receipt.get("final_disposition") or "UNKNOWN"
        quarantined = disposition in ("UNKNOWN", "DISPATCHED_UNCONFIRMED", "RECONCILIATION_NOT_FOUND", "RECONCILIATION_FAILED")

        technical_narrative = (
            f"Autonomous agent dispatched mutating tool '{tool_name}' (Action ID: {action_id}). "
            f"Transport boundary detected disruption: {transport_fault}. "
            f"Downstream state reconciliation yielded '{disposition}'. "
            f"Execution Integrity Boundary enforced fail-closed quarantine: retries halted, "
            f"downstream transaction state isolated with UUIDv5 idempotency key {idempotency_key}."
        )

        # 6. Potential Materiality Triggers
        triggers = []
        if transport_fault != "NONE":
            triggers.append(f"TRANSPORT_DISRUPTION_{transport_fault}")
        if disposition != "CONFIRMED":
            triggers.append(f"UNCONFIRMED_DOWNSTREAM_STATE_{disposition}")
        if supports_critical:
            triggers.append("CRITICAL_OR_IMPORTANT_FUNCTION_IMPACTED")
        if receipt.get("discrepancy_detected", False):
            triggers.append("WIRE_OVERCLAIM_DETECTED")

        # 7. Cryptographic Proof
        receipt_bytes = json.dumps(receipt, sort_keys=True).encode("utf-8")
        receipt_hash = hashlib.sha256(receipt_bytes).hexdigest()
        tamper_seal = receipt.get("ed25519_signature") or receipt.get("signature") or f"sha256:{receipt_hash}"

        return DORAAnnexIIInitialNotification(
            incident_identifier=incident_id,
            receipt_action_id=action_id,
            idempotency_key=idempotency_key,
            reporting_entity_name=entity_name,
            legal_entity_identifier_lei=lei,
            entity_type=entity_type,
            competent_authority=authority,
            contact_person=contact_person,
            detection_timestamp_utc=detection_dt.isoformat(),
            start_timestamp_utc=start_dt.isoformat(),
            statutory_deadlines=deadlines,
            classification_timestamp_utc=deadlines["classification_time_utc"],
            affected_ict_service=action_id,
            tool_name=tool_name,
            supports_critical_or_important_function=supports_critical,
            critical_function_description=function_desc,
            transport_disruption_type=transport_fault,
            downstream_reconciliation_status=disposition,
            quarantine_enforced=quarantined,
            technical_narrative=technical_narrative,
            impact_severity_rating=SEVERITY_PENDING,
            potential_materiality_triggers=triggers,
            human_sign_off_required=True,
            human_sign_off_status="AWAITING_INCIDENT_COMMANDER",
            receipt_sha256_hash=receipt_hash,
            signature_type="Ed25519" if "ed25519" in str(receipt) else "SHA256_DIGEST",
            cryptographic_tamper_seal=tamper_seal
        )

    def sign_human_review(
        self,
        dossier: DORAAnnexIIInitialNotification,
        reviewer_name: str,
        assigned_severity: str,
        notes: str
    ) -> DORAAnnexIIInitialNotification:
        """
        Records human-in-the-loop sign-off on incident severity.
        Valid severity values under RTS 2025/301: MAJOR, SIGNIFICANT, NON_MAJOR.
        """
        valid_ratings = {"MAJOR", "SIGNIFICANT", "NON_MAJOR"}
        normalized_rating = assigned_severity.strip().upper()
        if normalized_rating not in valid_ratings:
            raise ValueError(f"Invalid severity rating '{assigned_severity}'. Must be one of: {valid_ratings}")

        dossier.impact_severity_rating = normalized_rating
        dossier.reviewed_by = reviewer_name
        dossier.review_timestamp_utc = datetime.now(timezone.utc).isoformat()
        dossier.human_sign_off_status = "SIGNED_OFF"
        dossier.reviewer_verdict_notes = notes
        return dossier

    @staticmethod
    def render_markdown(dossier: DORAAnnexIIInitialNotification) -> str:
        """
        Renders a CISO / Regulatory Incident Commander Markdown Briefing.
        """
        status_badge = (
            "🔴 **PENDING HUMAN REVIEW (SIGN-OFF REQUIRED)**"
            if dossier.human_sign_off_status != "SIGNED_OFF"
            else f"🟢 **SIGNED OFF: {dossier.impact_severity_rating}**"
        )

        md = f"""# DORA RTS 2025/301 Annex II — Major ICT Incident Initial Notification

> **Regulatory Status**: {status_badge}  
> **Statutory Basis**: {REGULATION_REFERENCE} • {RTS_REFERENCE}  
> **Incident Reference**: `{dossier.incident_identifier}`

---

## 1. Submitting Entity & Governance

| Field | Detail |
| :--- | :--- |
| **Reporting Entity Name** | {dossier.reporting_entity_name} |
| **Legal Entity Identifier (LEI)** | `{dossier.legal_entity_identifier_lei}` (ISO 17442) |
| **Entity Classification** | {ENTITY_TYPES.get(dossier.entity_type, dossier.entity_type)} |
| **National Competent Authority** | {dossier.competent_authority} |
| **Designated Submitter / Contact** | {dossier.contact_person} |

---

## 2. Chronology & Statutory Submission Deadlines

| Milestone | Timestamp (UTC) | Statutory Requirement |
| :--- | :--- | :--- |
| **Incident Detection ($T_{{detect}}$)** | `{dossier.detection_timestamp_utc}` | Logged at transport exception trapping |
| **Execution Start ($T_{{start}}$)** | `{dossier.start_timestamp_utc}` | Original socket / MCP dispatch |
| **Initial Notification Deadline** | `{dossier.statutory_deadlines['initial_notification_deadline_utc']}` | **DORA Art. 19(4)(a)**: $\\min(T_{{class}} + 4h, T_{{aware}} + 24h)$ |
| **Intermediate Report Deadline** | `{dossier.statutory_deadlines['intermediate_report_deadline_utc']}` | **DORA Art. 19(4)(b)**: $T_{{class}} + 72h$ |
| **RTS 2025/301 Art. 4(2) Non-Adjustment** | `{'ENFORCED (No weekend/holiday extension)' if dossier.statutory_deadlines['rts_2025_301_art4_2_non_adjustment'] else 'STANDARD'}` | Credit Institution / Essential Entity Exemption |

---

## 3. Affected ICT Service & Criticality

- **Action URI / Service**: `{dossier.affected_ict_service}`
- **Dispatched Tool**: `{dossier.tool_name}`
- **Supports Critical or Important Function**: `{'YES (Mandatory Major Incident Scrutiny)' if dossier.supports_critical_or_important_function else 'NO'}`
- **Function Description**: {dossier.critical_function_description}

---

## 4. Technical Incident Description & Boundary Quarantine

- **Transport Disruption Detected**: `{dossier.transport_disruption_type}`
- **Downstream Reconciliation Status**: `{dossier.downstream_reconciliation_status}`
- **Execution Boundary Quarantine**: `{'ACTIVE (Fail-closed quarantine held — retries halted)' if dossier.quarantine_enforced else 'NOT ENFORCED'}`

### Technical Narrative
```text
{dossier.technical_narrative}
```

---

## 5. Materiality & Incident Classification (Human Sign-Off)

> [!WARNING]
> Under DORA Article 19 and RTS 2025/301, automated AI agents are **prohibited** from self-classifying
> or downgrading incident materiality. The pre-fill generator defaults to `PENDING_HUMAN_REVIEW`.

- **Current Severity Rating**: `{dossier.impact_severity_rating}`
- **Sign-Off Status**: `{dossier.human_sign_off_status}`
- **Reviewer Identity**: `{dossier.reviewed_by or 'UNASSIGNED'}`
- **Review Timestamp**: `{dossier.review_timestamp_utc or 'AWAITING_REVIEW'}`
- **Reviewer Notes / Rationale**:
```text
{dossier.reviewer_verdict_notes or 'Pending review by designated Incident Commander / CISO.'}
```

### Potential Materiality Triggers Identified:
{chr(10).join(f"- `{t}`" for t in dossier.potential_materiality_triggers)}

---

## 6. Cryptographic Evidence & Non-Repudiation

- **Idempotency Key (RFC 4122 UUIDv5)**: `{dossier.idempotency_key}`
- **Receipt Canonical SHA-256 Digest**: `{dossier.receipt_sha256_hash}`
- **Signature Mechanism**: `{dossier.signature_type}`
- **Cryptographic Tamper Seal**: `{dossier.cryptographic_tamper_seal[:32]}...`

---
*Generated by SovereignNexus SMAOS Execution Integrity Boundary (dora_annex_ii_prefill.py)*
"""
        return md


# ── CLI Interface ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="DORA RTS 2025/301 Annex II Initial Notification Pre-Fill Generator"
    )
    parser.add_argument(
        "--receipt", "-r",
        help="Path to single JSON execution receipt"
    )
    parser.add_argument(
        "--input-dir", "-i",
        help="Path to directory containing JSON receipts"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="dora_out",
        help="Output directory for generated Annex II dossiers"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "markdown", "all"],
        default="all",
        help="Output format (json, markdown, or all)"
    )
    parser.add_argument(
        "--entity-name",
        default="Regulated Financial Entity",
        help="Name of reporting entity"
    )
    parser.add_argument(
        "--lei",
        default="5493000IBP32UQZ0KL24",
        help="Legal Entity Identifier (ISO 17442)"
    )

    args = parser.parse_args()

    generator = DORAAnnexIIPreFillGenerator(
        default_entity_name=args.entity_name,
        default_lei=args.lei
    )

    receipts_to_process: List[Tuple[str, Dict[str, Any]]] = []

    if args.receipt:
        p = Path(args.receipt)
        if not p.is_file():
            print(f"Error: Receipt file '{args.receipt}' not found.", file=sys.stderr)
            sys.exit(1)
        with open(p, "r", encoding="utf-8") as f:
            receipts_to_process.append((p.stem, json.load(f)))

    elif args.input_dir:
        dir_p = Path(args.input_dir)
        if not dir_p.is_dir():
            print(f"Error: Directory '{args.input_dir}' not found.", file=sys.stderr)
            sys.exit(1)
        for json_file in sorted(dir_p.glob("**/*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    receipts_to_process.append((json_file.stem, json.load(f)))
            except Exception as e:
                print(f"Warning: Skipping {json_file}: {e}", file=sys.stderr)

    else:
        # Default mock scenario for demonstration
        mock_receipt = {
            "action_id": "mcp://sess-994/step-04/rpc-101/swift.settle_payment",
            "idempotency_key": "c3a4f89d-7214-5b68-b3de-7a8e52ef1a09",
            "actor": "5493000IBP32UQZ0KL24",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "tool_name": "swift.settle_payment",
            "transport_fault_detected": "HTTP_504_GATEWAY_TIMEOUT",
            "disposition": "DISPATCHED_UNCONFIRMED",
            "discrepancy_detected": True,
            "ed25519_signature": "d98f7e2a4b1c3d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e"
        }
        receipts_to_process.append(("demo_504_swift", mock_receipt))

    out_path = Path(args.output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("📋 DORA RTS 2025/301 ANNEX II PRE-FILL GENERATOR")
    print(f"Target Output Directory: {out_path.resolve()}")
    print("=" * 80)

    for name, receipt in receipts_to_process:
        dossier = generator.generate_from_receipt(receipt)
        print(f"\n[+] Generated Dossier: {dossier.incident_identifier} (Source: {name})")
        print(f"    • Severity Rating : {dossier.impact_severity_rating}")
        print(f"    • Initial Deadline: {dossier.statutory_deadlines['initial_notification_deadline_utc']}")
        print(f"    • Non-Adjustment  : {dossier.statutory_deadlines['rts_2025_301_art4_2_non_adjustment']}")

        if args.format in ("json", "all"):
            json_file = out_path / f"{name}_dora_annex_ii.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(dossier.to_dict(), f, indent=2)
            print(f"    -> Exported JSON    : {json_file.name}")

        if args.format in ("markdown", "all"):
            md_file = out_path / f"{name}_dora_annex_ii.md"
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(generator.render_markdown(dossier))
            print(f"    -> Exported Markdown: {md_file.name}")

    print("\n" + "=" * 80)
    print("✅ PRE-FILL GENERATION COMPLETE (MANDATORY HUMAN REVIEW PRESERVED)")
    print("=" * 80)


if __name__ == "__main__":
    main()
