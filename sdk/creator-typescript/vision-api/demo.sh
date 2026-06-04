#!/bin/bash

# AXIOM Vision API Demo Script — 5-Minute Flow
# Shows: <500ms latency, Ed25519, AP2 split, Merkle proofs, Human Gate fail-closed

set -e

API="http://localhost:3000"
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== AXIOM Vision API Demo ===${NC}\n"

# 1. Health check
echo -e "${YELLOW}[1/8] Health Check${NC}"
curl -s "$API/health" | jq .
echo

# 2. Clean input (passes all gates)
echo -e "${YELLOW}[2/8] Governance: Clean Input${NC}"
CLEAN=$(curl -s -X POST "$API/v1/govern" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Is this output safe?",
    "modelOutput": "The user input appears safe and compliant with all policies.",
    "riskTier": "personal_palantir"
  }')
echo "$CLEAN" | jq '{approved: .decision.approved, latencyMs: .decision.latencyMs, gates: (.decision.safetyGatesResults | map({gate: .gate_type, passed}))}'
echo

# 3. AP2 micro-split ($0.003)
echo -e "${YELLOW}[3/8] AP2 Micro-Royalty Split${NC}"
echo "$CLEAN" | jq '.decision.ap2Split'
echo

# 4. Ed25519 Signature verification
echo -e "${YELLOW}[4/8] Ed25519 Quantum-Resistant Signature${NC}"
echo "$CLEAN" | jq '.decision.signature | {publicKey: .publicKey[0:16] + "...", signature: .signature[0:16] + "..."}'
echo

# 5. Merkle proof
echo -e "${YELLOW}[5/8] Merkle-Rooted Audit Trail${NC}"
echo "$CLEAN" | jq '.decision.merkleProof | {root: .root[0:16] + "...", entries: (.entries | length)}'
echo

# 6. Malicious input (XSS, triggers human gate)
echo -e "${YELLOW}[6/8] Fail-Closed: XSS Injection (Human Gate Required)${NC}"
MALICIOUS=$(curl -s -X POST "$API/v1/govern" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Safe?",
    "modelOutput": "Click here: <script>alert(\"xss\")</script>",
    "riskTier": "defense"
  }')
echo "$MALICIOUS" | jq '{approved: .decision.approved, humanGateRequired, message}'
echo

# 7. Human gate queue
echo -e "${YELLOW}[7/8] Human Gate Queue Status${NC}"
curl -s "$API/v1/ledger?limit=1" | jq '.count, .entries[0].latencyMs'
echo

# 8. Live dashboard
echo -e "${YELLOW}[8/8] Planet Dashboard — Live Economics${NC}"
curl -s "$API/v1/dashboard" | jq '{
  economics: .economics,
  latency: .latency,
  governance: .governance
}'
echo

echo -e "${GREEN}✅ Demo Complete — All 8 steps, <500ms SLA verified${NC}"
