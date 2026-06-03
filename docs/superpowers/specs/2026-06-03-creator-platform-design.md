# Creator Platform — Design Spec v0 (June 3, 2026)

**Status:** Design Phase (starts Jun 3, implementation starts Jun 15 after Stream 2 SDK complete)  
**Owner:** Engineer 1  
**Timeline:** Design Jun 3–4, Impl Jun 15–29, Merge Jun 30

---

## Architecture Overview

**Goal:** Live creator dashboard showing 99% payout settlements, powered by AP2 Ledger + Creator SDK.

```
Creator Dashboard (Ratatui TUI + Web UI)
    ↓
Creator API (REST, JSON)
    ↓
Settlement Engine (AP2 Ledger stub)
    ↓
Merkle Audit Trail (signed Merkle roots)
```

---

## Components

### 1. Dashboard (Ratatui TUI)
- **Display:** Creator ID, balance, settlement history (last 10), real-time payout %
- **Inputs:** Creator login (email/token), refresh button
- **Outputs:** Settlement details with cryptographic proof (Merkle root hash)
- **Latency:** <100ms per screen refresh

### 2. Creator API (Axum REST)
- **Endpoint:** `GET /api/creator/{id}/balance` → `{balance_cents: i64, settlements: [...]}`
- **Endpoint:** `GET /api/creator/{id}/settlements` → List of all settlements with Merkle roots
- **Endpoint:** `POST /api/creator/{id}/withdraw` → Initiate payout (future: on-chain)
- **Auth:** Bearer token (Creator SDK signed)

### 3. Settlement Engine
- **Input:** Creator ID + settlement amount from AP2 Ledger
- **Output:** Creator payout (99%), platform fee (1%), Merkle-rooted proof
- **Integration:** Calls `siss-payment::AP2Ledger::settle()`

### 4. Audit Trail
- **Every settlement:** Log creator ID, amount, payout, Merkle root, timestamp
- **Tamper-proof:** Merkle chain verified on every read
- **GDPR:** Erasure requests trigger data deletion from logs

---

## Data Model

```rust
pub struct CreatorAccount {
    pub creator_id: Uuid,
    pub email: String,
    pub total_balance_cents: i64,
    pub settlements: Vec<Settlement>,
    pub merkle_root: [u8; 32],
}

pub struct Settlement {
    pub id: Uuid,
    pub amount_cents: i64,
    pub platform_fee_cents: i64,
    pub creator_payout_cents: i64,
    pub merkle_root: [u8; 32],
    pub timestamp: u64,
}
```

---

## MVP Features (Jun 30)

1. **Dashboard View**
   - Creator login
   - Display balance + last 10 settlements
   - Show 99% payout guarantee visually
   - Display Merkle root (hex string) for proof

2. **API Endpoints**
   - `GET /api/creator/{id}/balance` (authenticated)
   - `GET /api/creator/{id}/settlements` (paginated)

3. **Settlement Simulation**
   - Mock content upload → instant settlement via AP2 Ledger
   - Display payout breakdown (99% creator, 1% platform)

4. **50+ Creator Onboarding**
   - Batch user creation script
   - Generate test settlements
   - Verify all show correct 99% split

5. **Audit Trail**
   - Log every settlement
   - Merkle chain verification on startup
   - GDPR erasure support

---

## Dependencies

- **Stream 2 (SDK):** Must complete before implementation starts (Jun 14)
- **AP2 Ledger:** Already implemented (siss-payment crate)
- **Merkle audit:** Uses existing sha256 + Ed25519 signing

---

## Test Plan (TDD — write first, Jun 15–20)

```rust
#[test]
fn test_dashboard_displays_creator_balance() { /* expected payout = 99% */ }

#[test]
fn test_settlement_api_returns_correct_payout() { /* verify 1%/99% split */ }

#[test]
fn test_merkle_chain_verified_on_startup() { /* chain integrity */ }

#[test]
fn test_50_creators_onboarded_by_deadline() { /* batch creation */ }

#[test]
fn test_gdpr_erasure_removes_creator_record() { /* compliance */ }

#[test]
fn test_dashboard_refresh_latency_under_100ms() { /* performance */ }
```

---

## Success Criteria (June 30)

- ✅ Dashboard displays settlement history (>5 settlements per creator)
- ✅ API responds <100ms for balance query
- ✅ 50+ creators onboarded with verified settlements
- ✅ All settlements show exactly 99% creator payout
- ✅ Merkle chain verified unbroken (no tampering)
- ✅ GDPR erasure workflow functional (tested)
- ✅ Investor demo ready (live creator dashboard showing real payouts)

---

## Future (Post-Jun 30)

- Real payment integration (Stripe/Wise)
- Multi-currency support
- Creator analytics (earnings over time)
- Tax reporting export (1099-compatible)
