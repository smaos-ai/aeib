# Track Gamma: Sovereign Identity & Cross-Border DID Interoperability Mapping (`BSN` / `CTID` $\leftrightarrow$ `AEIB`)

> [!NOTE]
> **Epistemic Scope (`AGENTS.md` Rule 1 & Rule 5):**
> This specification defines the structural cryptographic and schema mapping between AEIB Root-Sponsor / Subagent capability credentials (`W3C DID` + `RFC 9052 COSE_Sign1`) and China's **Blockchain-based Service Network (`BSN` WenChang / Wuhan chains)**, **CTID (`National Network Identity`)** verifiable presentation envelopes, and **PIPL (`Personal Information Protection Law`)** cross-border data-minimization gates. Evaluated as a pre-production interoperability scaffold under the stated model.

---

## 1. Cross-Hemisphere Identity Translation Table

| Identity Layer | Western / Global Rail (`AP2` / `x402` / `W3C`) | Chinese Sovereign Rail (`BSN` / `CTID` / `GB/T 35273`) | AEIB Station 1/3 Translation Invariant |
| :--- | :--- | :--- | :--- |
| **Root Sponsor Identity** | `did:web:sponsor.example` or `did:key:z6Mk...` | `did:bsn:wenchang:<account_hash>` + `CTID` PID commitment |Station 1 binds both `sponsor_did` and `bsn_chain_account_digest` inside the signed `act_core` before computing `CAID`. |
| **Delegation Attenuation** | `AP2 v0.2` `IntentMandate` $\to$ `CartMandate` (`max_amount_minor`) | `e-CNY` / `BSN` Smart Contract Allowance (`max_fen_per_tx`, `expiry_epoch`) | Enforces $\text{amt}_{\text{minor}} \le \min(\text{max\_per\_call}, \text{bsn\_allowance\_minor})$. |
| **Cross-Border Data Gravity (`PIPL` Art. 38–40)** | `OTel GenAI v1.43` span/event split + `ZkTlsNotaryProxyPrototype` | `PIPL` & `DSL` on-shore raw PII residency requirement | Raw citizen/customer PII remains inside the on-shore vault; only salted SHA-256 commitments (`redacted_leaf_hashes`) and `BlindApiReceipt` proofs cross the boundary. |
| **Audit Non-Repudiation** | `IETF SCITT` (`RFC 9943` / `RFC 9942` header `394`) | `BSN` Consortium Merkle Anchor (`tx_receipt_root`) | Station 3 exports dual Merkle inclusion paths (`scitt_root` + `bsn_consortium_root`). |

---

## 2. Canonical Cross-Border Mandate Envelope (`canonical_json_v1`)

```json
{
  "action_type": "supply_chain.settle_invoice",
  "amount_minor": 85000,
  "bsn_interop": {
    "bsn_did": "did:bsn:wenchang:0x9f8c7b6a5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f00",
    "ctid_verified_commitment": "sha256:4a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b",
    "pipl_cross_border_mode": "BLIND_COMMITMENT_ONLY_ZERO_RAW_PII"
  },
  "currency": "CNY",
  "max_per_call_minor": 100000,
  "operation_id": "op-bsn-crossborder-01",
  "policy_epoch": "2026-Q4",
  "recipient": "bsn:merchant:shenzhen-electronics-01",
  "taint_tier": "TIER_1_REVIEWED"
}
```

## 3. Verification Invariants
1. **Zero Raw PII Egress:** Any cross-border settlement carrying `pipl_cross_border_mode != "BLIND_COMMITMENT_ONLY_ZERO_RAW_PII"` or containing unredacted national ID / phone fields is rejected fail-closed at Station 1 (`HALT_PIPL_RAW_PII_EGRESS_FORBIDDEN`).
2. **Dual DID Pinning:** Both the Western `sponsor_key_id` (`did:key`) and the `bsn_did` must match the pre-registered federation allowlist before TCC escrow reservation succeeds.
