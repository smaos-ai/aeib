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
aeib_iso20022_adapter.py — SOTA ISO 20022 XML & SWIFT CBPR+ Interbank Identifier Bridge
Part of the Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.

Translates between AEIB REST/JSON Canonical Action Identifiers (CAID) and
ISO 20022 financial message identifiers:
1. EndToEndId: Debtor-assigned end-to-end identification (max 35 alphanumeric characters)
   computed deterministically via Base32-encoded SHA-256 digest of CAID.
2. UETR: Unique End-to-end Transaction Reference (RFC 4122 UUIDv4) under SWIFT CBPR+
   computed deterministically from SHA-256(operation_id || caid).
3. XML Ingestion & Injection:
   - pain.001.001.09 (Customer Credit Transfer Initiation)
   - pacs.008.001.08 (Financial Institution Customer Credit Transfer)
   - pacs.002.001.10 (Payment Status Report - Reconciliation Probe)
   - camt.053.001.08 (Bank-to-Customer Statement - Out-of-Band Settlement)
"""

import base64
import hashlib
import uuid
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Tuple



def derive_iso20022_end_to_end_id(operation_id: str, action_caid: str) -> str:
    """
    Derives a deterministic, compliant ISO 20022 <EndToEndId> (max 35 alphanumeric characters).
    Format: AEIB + Base32(SHA256(operation_id || action_caid)[:19]) -> exactly 35 characters.
    """
    hasher = hashlib.sha256()
    hasher.update(operation_id.encode("utf-8"))
    hasher.update(b":")
    hasher.update(action_caid.encode("utf-8"))
    digest = hasher.digest()
    # 19 bytes base32 encoded is 31 chars; "AEIB" (4) + 31 chars = 35 chars
    b32_str = base64.b32encode(digest[:19]).decode("ascii").rstrip("=")
    return f"AEIB{b32_str[:31]}"


def derive_swift_uetr(operation_id: str, action_caid: str) -> str:
    """
    Derives a deterministic SWIFT CBPR+ compliant UUIDv4 (UETR).
    Conforms to RFC 4122 UUID Version 4 layout derived from SHA-256 digest.
    """
    hasher = hashlib.sha256()
    hasher.update(b"SWIFT_UETR_SALT_v1:")
    hasher.update(operation_id.encode("utf-8"))
    hasher.update(b":")
    hasher.update(action_caid.encode("utf-8"))
    raw_16 = bytearray(hasher.digest()[:16])
    # Set version to 4 (0100 in high 4 bits of time_hi_and_version)
    raw_16[6] = (raw_16[6] & 0x0F) | 0x40
    # Set variant to RFC 4122 (10xx in high 2 bits of clock_seq_hi_and_reserved)
    raw_16[8] = (raw_16[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(raw_16)))


class Iso20022PaymentAdapter:
    """
    Bidirectional transformer between AEIB Canonical Action Identifiers (CAID)
    and ISO 20022 XML / SWIFT payment messages.
    """

    XML_NAMESPACES = {
        "pain001": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09",
        "pacs008": "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08",
        "pacs002": "urn:iso:std:iso:20022:tech:xsd:pacs.002.001.10",
        "camt053": "urn:iso:std:iso:20022:tech:xsd:camt.053.001.08",
    }

    def __init__(self, institution_bic: str = "AEIBUS33XXX"):
        self.institution_bic = institution_bic

    def generate_pain001_xml(
        self,
        operation_id: str,
        action_caid: str,
        debtor_name: str,
        debtor_iban: str,
        creditor_name: str,
        creditor_iban: str,
        amount_minor: int,
        currency: str = "EUR",
    ) -> str:
        """
        Constructs a valid pain.001.001.09 XML document with deterministic
        <EndToEndId> and <UETR> bound to the action CAID.
        """
        end_to_end_id = derive_iso20022_end_to_end_id(operation_id, action_caid)
        uetr = derive_swift_uetr(operation_id, action_caid)
        amount_str = f"{amount_minor / 100:.2f}"

        root = ET.Element("Document", xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.09")
        cstmr_pmt_initn = ET.SubElement(root, "CstmrCdtTrfInitn")

        # Group Header
        grp_hdr = ET.SubElement(cstmr_pmt_initn, "GrpHdr")
        msg_id = ET.SubElement(grp_hdr, "MsgId")
        msg_id.text = f"MSG-{end_to_end_id}"
        cre_dt_tm = ET.SubElement(grp_hdr, "CreDtTm")
        cre_dt_tm.text = "2026-10-20T12:00:00Z"
        nb_of_txs = ET.SubElement(grp_hdr, "NbOfTxs")
        nb_of_txs.text = "1"
        ctrl_sum = ET.SubElement(grp_hdr, "CtrlSum")
        ctrl_sum.text = amount_str

        initg_pty = ET.SubElement(grp_hdr, "InitgPty")
        initg_nm = ET.SubElement(initg_pty, "Nm")
        initg_nm.text = debtor_name

        # Payment Information
        pmt_inf = ET.SubElement(cstmr_pmt_initn, "PmtInf")
        pmt_inf_id = ET.SubElement(pmt_inf, "PmtInfId")
        pmt_inf_id.text = f"PMT-{operation_id}"
        pmt_mtd = ET.SubElement(pmt_inf, "PmtMtd")
        pmt_mtd.text = "TRF"
        reqd_exctn_dt = ET.SubElement(pmt_inf, "ReqdExctnDt")
        dt = ET.SubElement(reqd_exctn_dt, "Dt")
        dt.text = "2026-10-20"

        # Debtor Info
        dbtr = ET.SubElement(pmt_inf, "Dbtr")
        dbtr_nm = ET.SubElement(dbtr, "Nm")
        dbtr_nm.text = debtor_name
        dbtr_acct = ET.SubElement(pmt_inf, "DbtrAcct")
        dbtr_id = ET.SubElement(dbtr_acct, "Id")
        dbtr_iban_elem = ET.SubElement(dbtr_id, "IBAN")
        dbtr_iban_elem.text = debtor_iban
        dbtr_agt = ET.SubElement(pmt_inf, "DbtrAgt")
        fin_instn_id = ET.SubElement(dbtr_agt, "FinInstnId")
        bic = ET.SubElement(fin_instn_id, "BICFI")
        bic.text = self.institution_bic

        # Credit Transfer Transaction Info
        cdt_trf_tx_inf = ET.SubElement(pmt_inf, "CdtTrfTxInf")
        pmt_id = ET.SubElement(cdt_trf_tx_inf, "PmtId")
        instr_id = ET.SubElement(pmt_id, "InstrId")
        instr_id.text = operation_id
        end_to_end_id_elem = ET.SubElement(pmt_id, "EndToEndId")
        end_to_end_id_elem.text = end_to_end_id
        uetr_elem = ET.SubElement(pmt_id, "UETR")
        uetr_elem.text = uetr

        amt = ET.SubElement(cdt_trf_tx_inf, "Amt")
        instd_amt = ET.SubElement(amt, "InstdAmt", Ccy=currency)
        instd_amt.text = amount_str

        cdtr = ET.SubElement(cdt_trf_tx_inf, "Cdtr")
        cdtr_nm = ET.SubElement(cdtr, "Nm")
        cdtr_nm.text = creditor_name
        cdtr_acct = ET.SubElement(cdt_trf_tx_inf, "CdtrAcct")
        cdtr_id = ET.SubElement(cdtr_acct, "Id")
        cdtr_iban_elem = ET.SubElement(cdtr_id, "IBAN")
        cdtr_iban_elem.text = creditor_iban

        return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")

    def extract_identifiers_from_xml(self, xml_content: str) -> Dict[str, Any]:
        """
        Parses an ISO 20022 XML document and extracts payment reference identifiers,
        reconstructing or verifying the bound CAID.
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as pe:
            return {"valid": False, "error": f"MALFORMED_XML: {pe}"}

        # Strip namespace if present
        def clean_tag(tag: str) -> str:
            return tag.split("}")[-1] if "}" in tag else tag

        extracted: Dict[str, Any] = {
            "end_to_end_id": None,
            "uetr": None,
            "instruction_id": None,
            "amount_str": None,
            "currency": None,
            "debtor_iban": None,
            "creditor_iban": None,
            "tx_status": None,
        }

        for elem in root.iter():
            tag = clean_tag(elem.tag)
            if tag == "EndToEndId" and elem.text:
                extracted["end_to_end_id"] = elem.text.strip()
            elif tag == "UETR" and elem.text:
                extracted["uetr"] = elem.text.strip()
            elif tag == "InstrId" and elem.text:
                extracted["instruction_id"] = elem.text.strip()
            elif tag == "InstdAmt" and elem.text:
                extracted["amount_str"] = elem.text.strip()
                extracted["currency"] = elem.attrib.get("Ccy")
            elif tag == "TxSts" and elem.text:
                extracted["tx_status"] = elem.text.strip()

        # Validation checks
        if not extracted["end_to_end_id"]:
            return {"valid": False, "error": "MISSING_END_TO_END_ID"}
        if len(extracted["end_to_end_id"]) > 35:
            return {"valid": False, "error": "END_TO_END_ID_EXCEEDS_35_CHARS"}

        return {"valid": True, "identifiers": extracted}

    def reconcile_pacs002_status_report(
        self,
        pacs002_xml: str,
        expected_operation_id: str,
        expected_caid: str,
    ) -> Dict[str, Any]:
        """
        Processes a pacs.002 Payment Status Report to reconcile an
        EFFECT_INDETERMINATE transaction into CONFIRMED (ACCP/ACSC) or REFUTED (RJCT).
        """
        res = self.extract_identifiers_from_xml(pacs002_xml)
        if not res.get("valid"):
            return {"disposition": "RECONCILIATION_FAILED", "reason": res.get("error")}

        idents = res["identifiers"]
        expected_e2e = derive_iso20022_end_to_end_id(expected_operation_id, expected_caid)
        expected_uetr = derive_swift_uetr(expected_operation_id, expected_caid)

        if idents["end_to_end_id"] != expected_e2e:
            return {
                "disposition": "RECONCILIATION_FAILED",
                "reason": "END_TO_END_ID_MISMATCH",
                "observed": idents["end_to_end_id"],
                "expected": expected_e2e,
            }

        if idents.get("uetr") and idents["uetr"].lower() != expected_uetr.lower():
            return {
                "disposition": "RECONCILIATION_FAILED",
                "reason": "UETR_MISMATCH",
                "observed": idents["uetr"],
                "expected": expected_uetr,
            }

        status = idents.get("tx_status")
        # ISO 20022 ExternalStatusReason1Code values:
        # ACCP: AcceptedCustomerProfile, ACSC: AcceptedSettlementCompleted
        # RJCT: Rejected, PDNG: Pending
        if status in ("ACCP", "ACSC", "ACTC"):
            return {
                "disposition": "RESOLVED_CONFIRMED",
                "iso_status": status,
                "end_to_end_id": idents["end_to_end_id"],
                "uetr": expected_uetr,
            }
        elif status in ("RJCT", "CANC"):
            return {
                "disposition": "RESOLVED_REFUTED",
                "iso_status": status,
                "end_to_end_id": idents["end_to_end_id"],
                "uetr": expected_uetr,
            }
        elif status in ("PDNG",):
            return {
                "disposition": "EFFECT_INDETERMINATE",
                "iso_status": status,
                "end_to_end_id": idents["end_to_end_id"],
                "uetr": expected_uetr,
            }

        return {
            "disposition": "EFFECT_INDETERMINATE",
            "iso_status": status or "UNKNOWN",
            "reason": "UNRECOGNIZED_TX_STATUS",
        }
