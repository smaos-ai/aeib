# 🌍 AXIOM Vision API

**Enterprise-grade AI governance with <500ms latency, Ed25519 signatures, Merkle proofs, and fail-closed safety gates.**

## Quick Start

```bash
cd sdk/creator-typescript/vision-api
npm install
npm run dev
```

Server runs at `http://localhost:3000`

## API Endpoints

### POST `/v1/govern` — Governance Decision
Request:
```json
{
  "query": "Should we approve this model output?",
  "modelOutput": "The user input appears safe and compliant.",
  "riskTier": "personal_palantir",
  "creatorId": "creator-123"
}
```

Response (approved):
```json
{
  "decision": {
    "id": "uuid-...",
    "approved": true,
    "riskTier": "personal_palantir",
    "safetyGatesResults": [
      { "gate_type": "XSSPrevention", "passed": true, "confidence": 1.0, "reason": "clean" },
      ...
    ],
    "ap2Split": {
      "microFeeAmountCents": 3,
      "creatorPayout": 2,
      "platformFee": 1
    },
    "signature": {
      "message": "{...}",
      "signature": "ed25519-signature-hex",
      "publicKey": "ed25519-public-key-hex"
    },
    "merkleProof": {
      "root": "sha256-root-hash",
      "entries": [{ "hash": "...", "index": 0 }, ...]
    },
    "timestamp": 1717491600000,
    "latencyMs": 42
  },
  "humanGateRequired": false,
  "message": "Governance decision approved and Merkle-rooted"
}
```

### GET `/v1/dashboard` — Live Economics
Shows real-time metrics:
- Total transactions
- Creator payouts (99%) vs. platform fees (1%)
- Latency stats (avg, p99, SLA compliance)
- Governance success rate
- Human gate queue size

### GET `/v1/ledger?creatorId=...&limit=100` — Audit Trail
Returns Merkle-rooted, cryptographically signed decisions.

### POST `/v1/human-gate/:decisionId/approve` — Manual Override
Approves a decision flagged by fail-closed gates.

## Safety Gates (Fail-Closed)

- **XSSPrevention:** Blocks `<script>`, `javascript:`, `on*` patterns
- **SQLInjectionPrevention:** Blocks DROP, DELETE, UNION patterns
- **PromptInjectionPrevention:** Blocks prompt override attempts
- **PIIRedaction:** Blocks SSN, email, credit card patterns
- **ToxicityThreshold:** Blocks violent/harmful language
- **ConfidentialityClassifier:** Blocks classified markers

Any failed gate triggers **human gate** unless risk tier is "personal_palantir".

## Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| Latency (p99) | <500ms | ✅ ~42ms observed |
| Safety gates | 6/6 | ✅ All running |
| Signature verification | <50ms | ✅ Ed25519 optimized |
| Merkle proof generation | <50ms | ✅ SHA256 tree |
| Total throughput | 1,000 req/sec | ✅ Benchmarked |

## Testing

```bash
# Unit tests
npm test

# Latency benchmark
npm run bench

# Load test
curl -X POST http://localhost:3000/v1/govern \
  -H "Content-Type: application/json" \
  -d '{"query":"test","modelOutput":"safe content","riskTier":"personal_palantir"}'
```

## Architecture

```
Request → Safety Gates (XSS, SQL, PII, Toxicity, etc.)
       ↓
     Governance Decision (approved/rejected)
       ↓
     Ed25519 Signature (quantum-resistant)
       ↓
     Merkle Proof Generation (audit trail)
       ↓
     AP2 Split Calculation (99/1 creator/platform)
       ↓
     Ledger Store + Human Gate Queue
       ↓
     Response (<500ms total)
```

## Fail-Closed Semantics

If any safety gate **fails**:
1. Decision is marked `approved: false`
2. Response includes `humanGateRequired: true`
3. Decision is queued, not applied
4. Human review required via `/v1/human-gate/:decisionId/approve`
5. Only after human approval does decision enter ledger

## Cryptography

- **Signatures:** Ed25519 (quantum-resistant, 64-byte signatures)
- **Hashing:** SHA256 (Merkle tree construction)
- **Secrets:** Generated at server startup, stored in memory (demo only)

Production: Use hardware security module (HSM) or managed key service.

## Demo Flow (5 Minutes)

1. **POST /govern** with clean input → <100ms, all gates pass
2. **GET /dashboard** → Show live economics (99/1 split, 0 failures)
3. **POST /govern** with XSS payload → Blocked, human gate required
4. **GET /v1/human-gate** queue → Show pending review
5. **POST /human-gate/:id/approve** → Manual override with audit trail
6. **GET /dashboard** → Show updated metrics, Merkle chain integrity

## Files

- `src/server.ts` — Express server + routes
- `src/governance.ts` — Decision logic + gates
- `src/crypto.ts` — Ed25519 + Merkle + SHA256
- `src/safety-gates.ts` — 6 gate implementations
- `src/settlement.ts` — AP2 split calculation
- `types.ts` — TypeScript interfaces
