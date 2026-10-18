# AEIB Wire-Level Interoperability: Google AP2 v0.2, Linux Foundation x402 V2, Stripe/OpenAI ACP & IETF SCITT

**Document Status:** Research Memo & Experimental Wire Specification (October 2026)  
**Target Subsystems:** `src/rail_mandate_and_mcp_taint_interlock.py`, `src/cbom_and_scitt_otel_exporter.py`, `tests/test_scitt_ap2_mcp_pqc_interop.py`, `tests/test_at64_rail_interop_and_mcp_tool_taint.py`  
**Epistemic Boundary:** Evaluated under the stated model; prototype interlock specification. All mechanisms are observed, tested, and configured within controlled environments.

---

## 1. Architectural Role: Co-Signer & Deterministic Gate (Not a Proprietary Island)

AEIB Station 1 and Station 2 operate natively on the wire formats of the primary agentic commerce protocols:

| Protocol | Wire Artifacts | AEIB Station 1 (Pre-Dispatch) Binding | AEIB Station 2 (Transport & 504 Reconciliation) |
| :--- | :--- | :--- | :--- |
| **Google AP2 v0.2** *(FIDO Alliance SD-JWT)* | `mandate.checkout.1`<br>`mandate.payment.1`<br>(`Open` $\rightarrow$ `Closed`) | Evaluates user-signed **Open Mandate** constraints; checks session context taint (`AT57b`) and MCP schema hash (`AT63`) before co-signing the **Closed Payment Mandate** (`checkout_hash == action_caid`). | On transport timeout, queries the Credential Provider / Merchant Payment Receipt endpoint using the `sd_hash` of the Closed Payment Mandate. |
| **Stripe / OpenAI ACP** *(agenticcommerce.dev)* | `POST /checkout_sessions/{id}/complete`<br>Header: `Idempotency-Key`<br>Body: `payment_data.token` (`SPT`) | Enforces mandatory `Idempotency-Key: aeib-idem-v1-<sha256(op_id:caid)>` and `Request-Id: <operation_id>` even though ACP marks them optional. | On `HTTP 504` / connection reset, latches `EFFECT_INDETERMINATE` and executes a single bounded probe to `GET /checkout_sessions/{checkout_session_id}` to inspect authoritative session state. |
| **Linux Foundation x402 V2** *(HTTP 402)* | `PAYMENT-REQUIRED`<br>`PAYMENT-SIGNATURE`<br>`PAYMENT-RESPONSE` | Decodes the Base64 `PAYMENT-REQUIRED` challenge, converts the price into minor EUR risk units, and charges it against the Root Sponsor's 5h Sprint + 7d Epoch pool (`AT56`) before signing `PAYMENT-SIGNATURE`. | If the request drops before `PAYMENT-RESPONSE` arrives, blocks re-signing a new voucher/nonce until facilitator settlement state is queried via deterministic payment-identifier. |
| **IETF SCITT Profile** *(RFC 9942 / RFC 9943)* | Transparent Statement CBOR<br>Header `394` (`receipts`)<br>Header `395` (`vds=1`)<br>Header `396` (`vdp`) | Submits the `COSE_Sign1` receipt to an external or local Transparency Service, receiving a cryptographic Merkle tree inclusion proof. | Provides offline-verifiable proof of finality; logs transparent statements to OpenTelemetry GenAI spans for auditor ingestion. |

### 1.1 The Layer 3 Wire & Ledger Interlock

As autonomous agents transition from conversational retrieval to direct financial settlement and infrastructure actuation, industry payment protocols have converged around three primary Layer 3 rails:
1. **Google Agent Payments Protocol (AP2 v0.2)** — FIDO Alliance SD-JWT Verifiable Digital Credentials (`mandate.checkout.1`, `mandate.payment.1`) and 3-tier mandate chains (`IntentMandate` $\rightarrow$ `CartMandate` $\rightarrow$ `PaymentMandate`).
2. **Linux Foundation / Coinbase x402 V2 (`HTTP 402 Payment Required`)** — Machine-to-machine HTTP header settlement (`PAYMENT-REQUIRED` / `PAYMENT-SIGNATURE` / `PAYMENT-RESPONSE`) with EIP-3009 authorization payloads.
3. **Stripe / OpenAI / Meta Agentic Commerce Protocol (ACP)** — Delegated `Shared Payment Tokens` (`spt_...`) over versioned REST checkout endpoints (`API-Version: 2025-09-29`).

While each rail defines how a merchant or settlement facilitator validates payment authorization, none inspect the **internal runtime integrity** of the calling agent (such as whether the agent's context was poisoned by an untrusted Model Context Protocol tool output, or whether a local transport timeout left a stateful token in an indeterminate state).

The **Agent Execution Integrity Boundary (AEIB)** operates at **Layer 3 (Wire & Ledger Plane)**—immediately upstream of the outbound network socket—acting as a cryptographic co-signer, deterministic idempotency binder, and provenance taint governor across all three rails.

```mermaid
flowchart LR
    subgraph AgentRuntime["Agent Runtime & MCP Context"]
        MCP["MCP Tool Invocation (AT63/AT64)"]
        Taint["Provenance Taint Tracker"]
        MCP --> Taint
    end

    subgraph AEIB["AEIB Station 1 (Layer 2.5 / Layer 3 Interlock)"]
        Verify["Mandate & Ceiling Verifier"]
        JCS["RFC 8785 JCS + CAID Binder"]
        Cosign["Ed25519 COSE_Sign1 Co-Signer"]
        Latch["EFFECT_INDETERMINATE Latch"]
        Verify --> JCS --> Cosign --> Latch
    end

    subgraph Rails["Layer 3 Settlement Rails"]
        AP2["Google AP2 Mandate Chain"]
        X402["LF / Coinbase x402 v2"]
        ACP["Stripe / OpenAI ACP"]
    end

    subgraph SCITTProfile["Optional External Transparency Profile"]
        SCITT["IETF SCITT Transparency Service (RFC 9942/9943)"]
        OTel["OpenTelemetry GenAI Spans"]
    end

    Taint --> Verify
    Latch --> AP2
    Latch --> X402
    Latch --> ACP
    Cosign -.-> SCITT
    Cosign -.-> OTel
```

---

## 2. Google AP2 (Agent Payments Protocol) Wire Mapping

Under Google AP2, financial authority flows through a three-tier cryptographic mandate chain:
- **`IntentMandate`**: Issued by the user or delegating authority, establishing `id`, `allowedMerchants`, `amountLimit`, `currency`, and `expiresAt`.
- **`CartMandate`**: Binds SKU line items (`items: [{sku, price_minor, quantity}]`), `merchant`, and total `amount` (`{currency, value_minor}`) to `parentIntentId`.
- **`PaymentMandate`**: Authorizes final rail settlement against `parentCartId` and `parentIntentId`.

### 2.1 Station 1 Verification Rules (`AP2MandateChainVerifier`)
Before AEIB co-signs an outbound AP2 dispatch, Station 1 evaluates the full 3-tier chain under the stated model:
1. **Cryptographic Signature Verification:** Each mandate (`IntentMandate`, `CartMandate`, `PaymentMandate`) carries an Ed25519 signature over the RFC 8785 JCS canonicalization (`encode_jcs`) of its unsigned payload. Invalid signatures trigger `HALT_AP2_MANDATE_SIGNATURE_INVALID`.
2. **Lineage Continuity:** `CartMandate.parentIntentId` must equal `IntentMandate.id`, and `PaymentMandate.parentCartId` must equal `CartMandate.id` (with `PaymentMandate.parentIntentId == IntentMandate.id`).
3. **Merchant Allowlist Enforcement:** `CartMandate.merchant` and `PaymentMandate.merchant` must be members of `IntentMandate.allowedMerchants`. Violations trigger `HALT_AP2_MERCHANT_NOT_ALLOWED`.
4. **SKU Line-Item Arithmetic Integrity:** The sum of SKU line items in `CartMandate.items` must exactly equal the declared cart and payment value:
   $$\sum_{i} \left(\text{price\_minor}_i \times \text{quantity}_i\right) = \text{CartMandate.amount.value\_minor} = \text{PaymentMandate.amount.value\_minor}$$
   Any discrepancy (e.g., hidden fee injection or hallucinated discount arithmetic) triggers `HALT_AP2_SKU_TOTAL_MISMATCH`.
5. **Intent Limit Ceiling & Freshness:** The verified total must satisfy $\text{amount.value\_minor} \le \text{IntentMandate.amountLimit}$ (otherwise `HALT_AP2_CART_EXCEEDS_INTENT_LIMIT`), and the evaluation timestamp must precede `expiresAt`.
6. **Deterministic Idempotency Derivation:** AEIB derives the wire header:
   ```text
   Idempotency-Key: aeib-idem-v1-<sha256(operation_id:action_caid)[:32]>
   ```
   and encapsulates all three mandate digests inside an RFC 9052 `COSE_Sign1`-compatible receipt.

### 2.2 The Six AP2 Open Questions (Research Agenda)

While the AP2 specification provides a compelling mandate model, six critical technical questions remain open in the live specification:

1. **Revocation Distribution Mechanics:**
   - *Question:* How are revoked `IntentMandates` distributed to edge agents and participating merchants prior to TTL expiry without introducing high-latency online CRL/OCSP query bottlenecks?
   - *AEIB Research Approach:* AEIB prototypes local epoch-bounded revocation vectors (`PolicyEpochFresh`) where mandate lifetimes are bounded to short intervals (e.g., 300 seconds), supplemented by single-use ticket burn at Station 1.
2. **Multi-Merchant Cart Splitting:**
   - *Question:* How does `CartMandate` handle multi-merchant checkouts across federated shopping carts without cart-hash desynchronization or fragmented authorization chains?
   - *AEIB Research Approach:* AEIB requires atomic partition allocation: if a transaction involves multiple merchant endpoints, it decomposes into disjoint sub-intents with explicit partial budgets, co-signing each checkout hash independently.
3. **Partial Fulfillment & Refund Binding:**
   - *Question:* How are partial fulfillments, out-of-stock cancellations, and subsequent refund receipts cryptographically linked back to the original Closed Payment Mandate `sd_hash`?
   - *AEIB Research Approach:* Station 1 generates an explicit downstream settlement entry referencing the original `operation_id` and `action_caid`, requiring an Ed25519 target-signed refutation/settlement attestation (`AT58`).
4. **Holder Key Custody & Authenticator Levels:**
   - *Question:* Where is the agent's signing key held during autonomous execution (TEE vs HSM vs secure software enclave), and does software key custody in an agent runner violate FIDO Level 2+ authenticator requirements?
   - *AEIB Research Approach:* AEIB enforces credential starvation on the agent process (`Agent_Process ∩ {keys} == ∅`), retaining the signing key in the isolated Station 2 sidecar. We document software keys as prototype implementations and map hardware HSM/CVM configurations as operational prerequisites for FIDO conformance.
5. **Offline Verification Latency Under Burst Loads:**
   - *Question:* What is the verification latency of parsing and validating nested SD-JWT disclosures on high-throughput payment gateways during traffic bursts?
   - *AEIB Research Approach:* Benchmarks show pure-Python SD-JWT parsing adds 1.2–3.8 ms per evaluation; compiling verification paths to Rust/WASM reduces overhead to sub-millisecond ranges.
6. **Schema Evolution & Version Migration:**
   - *Question:* How does AP2 manage schema migrations (`vct: mandate.checkout.1` $\rightarrow$ `vct: mandate.checkout.2`) without breaking in-flight transactions or cached merchant policies?
   - *AEIB Research Approach:* AEIB binds explicit schema digests into the pre-dispatch intent, rejecting unversioned or unexpected schema variants fail-closed.

---

## 3. Linux Foundation / Coinbase x402 v2 (`HTTP 402 Payment Required`) Wire Mapping

The x402 v2 specification standardizes machine-to-machine micropayments and API settlement over HTTP using structured headers:
- **Server Challenge (`PAYMENT-REQUIRED`):** JSON payload declaring `x402Version: 2` and an `accepts` array of settlement options.
- **Client Authorization (`PAYMENT-SIGNATURE`):** Carries an EIP-3009 (`transferWithAuthorization` / `receiveWithAuthorization`) or permit payload containing `scheme`, `network`, `amount_minor`, `pay_to`, `nonce`, `valid_after`, `valid_before`, and an AEIB extension field `bound_action_caid`.

### 3.1 Station 1 Verification Rules (`X402V2WireInterlock`)
To prevent double-settlement during HTTP 504 gateway timeouts or TCP reset faults, `X402V2WireInterlock` enforces:
1. **Content-Addressable Action Binding (`bound_action_caid`):** The `PAYMENT-SIGNATURE` payload must bind `bound_action_caid == "sha256:" + sha256(encode_jcs(action_payload))`. If a retry loop attempts to reuse a signed `PAYMENT-SIGNATURE` header against a mutated request body or different endpoint, Station 1 halts with `HALT_X402_CAID_MISMATCH`.
2. **EIP-3009 Nonce Deduplication & Replay Protection:** Every `(nonce, bound_action_caid)` pair is tracked in the interlock ledger. Replaying a `nonce` for a different `bound_action_caid` triggers `HALT_X402_NONCE_REPLAY`.
3. **Scheme & Ceiling Validation (`exact` vs. `upto` vs. `auth-capture`):**
   - For `scheme == "exact"`, `amount_minor` must equal the challenge `amount`.
   - For `scheme in {"upto", "auth-capture"}`, `amount_minor` must not exceed the challenge `amount`.
   - Exceeding the challenge amount triggers `HALT_X402_AMOUNT_EXCEEDS_CHALLENGE`.
4. **Time-Window & Cryptographic Verification:** `valid_after <= current_timestamp <= valid_before`, and the Ed25519 signature over `encode_jcs` of the unsigned `PAYMENT-SIGNATURE` payload must verify.

### 3.2 Payment-Identifier Mapping & Idempotent Retries
In x402 v2, idempotent re-transmission is achieved by coupling the `payment-identifier` extension with the AEIB `operation_id` and `action_caid`:
- When a client sends a `PAYMENT-SIGNATURE`, it sets:
  ```http
  PAYMENT-SIGNATURE: <base64(payload)>
  Idempotency-Key: aeib-idem-v1-<sha256(operation_id:action_caid)[:32]>
  Payment-Identifier: <sha256(nonce:action_caid)[:32]>
  ```
- If an HTTP 504 timeout occurs, the payment identifier ensures that an upstream facilitator that processed the settlement returns the cached settlement receipt (`PAYMENT-RESPONSE`) rather than initiating a second transfer.

### 3.3 Fallback Behavior for Unsupported Targets
When an external target or facilitator **does not support x402**, does not implement RFC 9396 Rich Authorization Requests, or ignores `Idempotency-Key` headers:
1. **No Speculative Assumption:** AEIB never assumes that an uninstrumented target successfully executed or dropped a timed-out mutation.
2. **Fail-Closed Wire Latch:** If a transport fault occurs against an uninstrumented target, the boundary latches to `EFFECT_INDETERMINATE`.
3. **Escrow Retention:** The allocated spend remains locked in the Root Sponsor's quota escrow (`AT58`).
4. **Manual or Out-of-Band Inquiry:** Because the target lacks an idempotent query endpoint, the transaction cannot be resolved by an automated probe without risking side effects. It escalates to human operator intervention or an out-of-band balance reconciliation workflow before escrowed budget is released.

---

## 4. Stripe / OpenAI ACP (Agentic Commerce Protocol) Wire Mapping

Under the Stripe / OpenAI Agentic Commerce Protocol (`API-Version: 2025-09-29`), agents complete merchant checkouts via `POST /checkout_sessions/{id}/complete` using a single-use, merchant-scoped `Shared Payment Token` (`spt_...`).

### 4.1 Station 1 Verification Rules (`StripeACPCheckoutInterlock`)
1. **Version & Deterministic Idempotency Binding:** Every outbound `POST /checkout_sessions/{id}/complete` request is bound to `API-Version: 2025-09-29` and a deterministic `Idempotency-Key` derived from `(checkout_session_id, spt_id, action_caid)`.
2. **Single-Use SPT `EFFECT_INDETERMINATE` Latch:** If the HTTP transport returns a timeout, HTTP 502/504, or connection reset during `POST /checkout_sessions/{id}/complete`, the side effect on the merchant server is indeterminate. Because an agent retry loop often reacts to a failure by either re-submitting `spt_id` without idempotency alignment or minting a *second* `spt_...` for the same checkout session, AEIB immediately transitions the checkout session and `spt_id` into `EFFECT_INDETERMINATE`.
3. **Fail-Closed Retry Blocking (`HALT_ACP_SPT_LOCKED_INDETERMINATE`):** Any subsequent attempt to call `complete_checkout` on that session or `spt_id`—including attempts supplying a newly minted `spt_...`—is blocked with `HALT_ACP_SPT_LOCKED_INDETERMINATE`.
4. **Out-of-Band Probe Reconciliation:** The lock is only cleared when an authoritative out-of-band status probe (`reconcile_checkout_session_probe`) verifies the remote `GET /checkout_sessions/{id}` state (`completed` vs. `open_unpaid`) signed by the probe verifier.

---

## 5. Directive 3 — MCP Tool Supply-Chain & Provenance-Tiered Consequence Ceiling (`AT63` & `AT64`)

Model Context Protocol (MCP) ecosystems expose two critical attack vectors against financial agents:
- **AT63 (Shadow MCP Server & Tool Description Poisoning / Rug-Pulls):** Unregistered MCP servers ("Shadow MCP") or mutated tool definitions (`description` / `inputSchema`) that embed covert prompt-injection instructions (e.g., *"Before calling this tool, transfer funds to..."* or hidden parameter defaults) as documented by Invariant Labs and the OWASP MCP Top 10.
- **AT64 (Untrusted Tool Output Provenance Taint):** Even when an MCP tool descriptor is benign, invoking a `TIER_2_UNTRUSTED_EXTERNAL` tool (such as a web scraper, third-party email reader, or unverified community connector) introduces untrusted external data into the LLM context window.

### 5.1 Station 1 Enforcement (`MCPToolProvenanceTaintGate`)

| Threat Vector | Detection Mechanism | AEIB Rejection Code |
| :--- | :--- | :--- |
| Unregistered / Shadow MCP Server | Server ID not present in approved registry or missing valid Ed25519 registration | `HALT_SHADOW_MCP_SERVER_UNREGISTERED` |
| MCP Tool Description / Schema Poisoning | Static inspection of `description` and serialized `input_schema` for covert override directives (`ignore previous`, `system prompt`, `transfer funds`, `<system>`, etc.) | `HALT_MCP_TOOL_DESCRIPTION_POISONING` |
| Post-Approval Tool Rug-Pull | Live `(description, input_schema, source_sha256)` JCS digest mismatches pinned `MCPToolDescriptor` signature | `HALT_MCP_TOOL_RUG_PULL_DETECTED` |
| Untrusted Tool Output Context Taint (`AT64`) | Session invokes a `TIER_2_UNTRUSTED_EXTERNAL` tool, degrading session consequence ceiling from `HIGH_FINANCIAL` to `LOW_READ_ONLY` | `UNTRUSTED_TOOL_TAINT_CEILING_DEGRADED` |

### 5.2 Provenance-Tiered Consequence Ceiling Degradation (`AT64`)
1. Every registered MCP tool is assigned a provenance tier:
   - `TIER_0_SYSTEM_PINNED`: Local deterministic AEIB / core system tools.
   - `TIER_1_PARTNER_ATTESTED`: Cryptographically attested partner endpoints.
   - `TIER_2_UNTRUSTED_EXTERNAL`: External retrieval, web, or third-party tools whose outputs may carry indirect prompt injections.
2. When a session invokes any `TIER_2_UNTRUSTED_EXTERNAL` tool, `MCPToolProvenanceTaintGate` marks the session as tainted (`session_tainted = True`) and lowers the session's maximum permitted financial consequence ceiling (`effective_ceiling_minor`).
3. Any subsequent attempt to execute a high-consequence financial action (across AP2, x402 v2, or Stripe ACP) exceeding the degraded ceiling is halted with `UNTRUSTED_TOOL_TAINT_CEILING_DEGRADED` unless a valid Ed25519 human supervisor step-up token (`verify_step_up_token`) is presented for that exact `action_caid`.

---

## 6. Optional Transparency Profile: IETF SCITT (RFC 9942 / RFC 9943)

### 6.1 Role of SCITT in AEIB
AEIB can be configured with an optional **IETF SCITT (Supply Chain Integrity, Transparency, and Trust)** transparency profile:
- Receipts emitted by Station 1 or Station 3 are encoded as RFC 9052 `COSE_Sign1` envelopes.
- An optional SCITT Transparency Service (RFC 9943) maintains a binary SHA-256 Merkle tree (RFC 9162).
- When a signed receipt is registered, the Transparency Service issues an RFC 9942 COSE Receipt containing an inclusion proof (`leaf_index`, `tree_size`, `audit_path`).
- The receipt is embedded directly into the statement's unprotected header `394` (`COSE_HEADER_RECEIPTS`), with header `395` (`COSE_HEADER_VDS = 1`) and header `396` (`COSE_HEADER_VDP`), forming a self-contained **Transparent Statement**.

### 6.2 Trust Boundary & Epistemic Limitations of SCITT
Integrating SCITT alters the trust profile of the audit trail, but its boundaries must be stated with technical precision:
1. **Non-Repudiation for Registered Statements:** Once a statement is logged and its inclusion proof verified against the signed Merkle root, an operator or attacker cannot silently modify or delete that receipt without invalidating the Merkle tree.
2. **Does NOT Eliminate Local Host Trust:** SCITT does not prevent a fully compromised host from dropping receipts prior to submission, fabricating false telemetry, or attempting direct socket egress if local container/sandbox isolation is breached.
3. **Does NOT Validate Upstream Truth:** The SCITT log attests that *a specific statement was registered at a specific sequence and time*; it does not verify whether the agent's prompt reasoning was epistemically correct.
4. **Availability & Latency Tradeoff:** Registering every discrete mutation synchronously against an external transparency service introduces network dependency. AEIB therefore supports asynchronous epoch batching or local root checkpointing for high-throughput environments.
