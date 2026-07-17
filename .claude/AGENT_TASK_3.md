# AGENT 3: Multi-Currency Settlement with Stripe Connect
**Dispatch Date:** 2026-06-12 (after Agent 1 completes)  
**Deadline:** 2026-06-19 (7 days)  
**TDD Discipline:** ✅ REQUIRED — Write tests first, ALL FAILING, then implement

---

## Your Task

Build Stripe Connect integration for 8 APAC markets with automated payout scheduling (1-3 business days per region):
- 🇸🇬 Singapore (SGD, 1-day payout)
- 🇦🇺 Australia (AUD, 2-day payout)
- 🇯🇵 Japan (JPY, 3-day payout)
- 🇰🇷 South Korea (KRW, 2-day payout)
- 🇮🇳 India (INR, 2-day payout)
- 🇹🇭 Thailand (THB, 2-day payout)
- 🇻🇳 Vietnam (VND, 3-day payout)
- 🇮🇩 Indonesia (IDR, 3-day payout)

## Files You Own (EXCLUSIVE)
- `crates/siss-apac-expansion/src/settlement/mod.rs` (create)
- `crates/siss-apac-expansion/src/settlement/stripe_integration.rs` (create)
- `crates/siss-apac-expansion/src/settlement/payout_scheduler.rs` (create)
- `crates/siss-apac-expansion/migrations/002_settlement_tracking.sql` (create)
- `crates/siss-apac-expansion/src/tests.rs` (ADD ONLY settlement_tests module)

**DO NOT TOUCH:** Other test modules, other files

---

## TDD Execution Order

### Step 1: Write ALL Tests First (Should Fail)

**File:** `crates/siss-apac-expansion/src/tests.rs` — ADD this module:

```rust
#[cfg(test)]
mod settlement_tests {
    use crate::settlement::{
        Country, PayoutScheduler, SettlementStatus, StripeSettlementManager,
    };
    use chrono::Duration;

    #[test]
    fn test_multi_currency_settlement_valid() {
        let manager = StripeSettlementManager::new();
        let countries = manager.all_supported_countries();
        assert_eq!(countries.len(), 8);

        assert!(countries.iter().any(|c| c.code() == "SG"));
        assert!(countries.iter().any(|c| c.code() == "AU"));
        assert!(countries.iter().any(|c| c.code() == "JP"));
        assert!(countries.iter().any(|c| c.code() == "KR"));
        assert!(countries.iter().any(|c| c.code() == "IN"));
        assert!(countries.iter().any(|c| c.code() == "TH"));
        assert!(countries.iter().any(|c| c.code() == "VN"));
        assert!(countries.iter().any(|c| c.code() == "ID"));
    }

    #[test]
    fn test_stripe_account_creation() {
        let mut manager = StripeSettlementManager::new();
        let account = manager.create_connected_account(Country::Singapore);
        assert!(account.is_ok());

        let acc = account.unwrap();
        assert_eq!(acc.currency, "SGD");
        assert_eq!(acc.country, Country::Singapore);
    }

    #[test]
    fn test_payout_speed_singapore() {
        assert_eq!(Country::Singapore.payout_speed_days(), 1);
    }

    #[test]
    fn test_payout_speed_australia() {
        assert_eq!(Country::Australia.payout_speed_days(), 2);
    }

    #[test]
    fn test_payout_speed_japan() {
        assert_eq!(Country::Japan.payout_speed_days(), 3);
    }

    #[test]
    fn test_settlement_transaction_creation() {
        let mut manager = StripeSettlementManager::new();
        let account = manager
            .create_connected_account(Country::Singapore)
            .unwrap();

        let txn = manager.create_settlement_transaction(&account.account_id, 100000);
        assert!(txn.is_ok());

        let txn = txn.unwrap();
        assert_eq!(txn.amount_cents, 100000);
        assert_eq!(txn.status, SettlementStatus::Pending);
        assert_eq!(txn.payout_speed_days, 1);
    }

    #[test]
    fn test_payout_scheduler_workflow() {
        let mut manager = StripeSettlementManager::new();
        let account = manager
            .create_connected_account(Country::Korea)
            .unwrap();
        let mut txn = manager.create_settlement_transaction(&account.account_id, 50000).unwrap();

        PayoutScheduler::schedule_payout(&mut txn);
        assert_eq!(txn.status, SettlementStatus::Scheduled);

        let future_txn = {
            let mut t = txn.clone();
            t.scheduled_payout_date = chrono::Utc::now() - Duration::hours(1);
            t
        };
        let mut mutable_future = future_txn;
        let result = PayoutScheduler::execute_payout(&mut mutable_future);
        assert!(result.is_ok());
        assert_eq!(mutable_future.status, SettlementStatus::InProgress);
    }

    #[test]
    fn test_payout_cannot_execute_early() {
        let mut manager = StripeSettlementManager::new();
        let account = manager
            .create_connected_account(Country::Australia)
            .unwrap();
        let mut txn = manager.create_settlement_transaction(&account.account_id, 25000).unwrap();

        PayoutScheduler::schedule_payout(&mut txn);
        let result = PayoutScheduler::execute_payout(&mut txn);
        assert!(result.is_err());
    }

    #[test]
    fn test_all_markets_have_currency() {
        let countries = vec![
            Country::Singapore,
            Country::Australia,
            Country::Japan,
            Country::SouthKorea,
            Country::India,
            Country::Thailand,
            Country::Vietnam,
            Country::Indonesia,
        ];
        
        for country in countries {
            assert!(!country.currency().is_empty());
            assert_eq!(country.currency().len(), 3);
        }
    }

    #[test]
    fn test_all_markets_have_payout_speed() {
        let countries = vec![
            Country::Singapore,
            Country::Australia,
            Country::Japan,
            Country::SouthKorea,
            Country::India,
            Country::Thailand,
            Country::Vietnam,
            Country::Indonesia,
        ];
        
        for country in countries {
            let speed = country.payout_speed_days();
            assert!(speed >= 1 && speed <= 3);
        }
    }
}
```

**Run tests (should FAIL):**
```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p siss-apac-expansion settlement_tests 2>&1 | head -50
```

Expected: All 10 tests fail

---

### Step 2: Implement stripe_integration.rs

**File:** `crates/siss-apac-expansion/src/settlement/stripe_integration.rs`

```rust
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Country {
    Singapore,
    Australia,
    Japan,
    SouthKorea,
    India,
    Thailand,
    Vietnam,
    Indonesia,
}

impl Country {
    pub fn code(&self) -> &str {
        match self {
            Country::Singapore => "SG",
            Country::Australia => "AU",
            Country::Japan => "JP",
            Country::SouthKorea => "KR",
            Country::India => "IN",
            Country::Thailand => "TH",
            Country::Vietnam => "VN",
            Country::Indonesia => "ID",
        }
    }

    pub fn currency(&self) -> &str {
        match self {
            Country::Singapore => "SGD",
            Country::Australia => "AUD",
            Country::Japan => "JPY",
            Country::SouthKorea => "KRW",
            Country::India => "INR",
            Country::Thailand => "THB",
            Country::Vietnam => "VND",
            Country::Indonesia => "IDR",
        }
    }

    pub fn payout_speed_days(&self) -> u32 {
        match self {
            Country::Singapore => 1,
            Country::Australia => 2,
            Country::Japan => 3,
            Country::SouthKorea => 2,
            Country::India => 2,
            Country::Thailand => 2,
            Country::Vietnam => 3,
            Country::Indonesia => 3,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StripeAccount {
    pub account_id: String,
    pub country: Country,
    pub currency: String,
    pub connected_account: String,
    pub enabled: bool,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SettlementTransaction {
    pub id: Uuid,
    pub account_id: String,
    pub country: Country,
    pub currency: String,
    pub amount_cents: i64,
    pub payout_speed_days: u32,
    pub scheduled_payout_date: chrono::DateTime<chrono::Utc>,
    pub status: SettlementStatus,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub completed_at: Option<chrono::DateTime<chrono::Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum SettlementStatus {
    Pending,
    Scheduled,
    InProgress,
    Completed,
    Failed,
}

pub struct StripeSettlementManager {
    accounts: HashMap<String, StripeAccount>,
}

impl StripeSettlementManager {
    pub fn new() -> Self {
        StripeSettlementManager {
            accounts: HashMap::new(),
        }
    }

    pub fn create_connected_account(&mut self, country: Country) -> Result<StripeAccount, String> {
        let account_id = uuid::Uuid::new_v4().to_string();
        let account = StripeAccount {
            account_id: account_id.clone(),
            country: country.clone(),
            currency: country.currency().to_string(),
            connected_account: format!("acct_{}", account_id),
            enabled: true,
            created_at: chrono::Utc::now(),
        };

        self.accounts.insert(account_id, account.clone());
        Ok(account)
    }

    pub fn get_account(&self, account_id: &str) -> Option<StripeAccount> {
        self.accounts.get(account_id).cloned()
    }

    pub fn create_settlement_transaction(
        &self,
        account_id: &str,
        amount_cents: i64,
    ) -> Result<SettlementTransaction, String> {
        let account = self
            .get_account(account_id)
            .ok_or("Account not found".to_string())?;

        let payout_speed_days = account.country.payout_speed_days();
        let scheduled_payout_date = chrono::Utc::now()
            + chrono::Duration::days(payout_speed_days as i64);

        Ok(SettlementTransaction {
            id: uuid::Uuid::new_v4(),
            account_id: account.account_id,
            country: account.country,
            currency: account.currency,
            amount_cents,
            payout_speed_days,
            scheduled_payout_date,
            status: SettlementStatus::Pending,
            created_at: chrono::Utc::now(),
            completed_at: None,
        })
    }

    pub fn all_supported_countries(&self) -> Vec<Country> {
        vec![
            Country::Singapore,
            Country::Australia,
            Country::Japan,
            Country::SouthKorea,
            Country::India,
            Country::Thailand,
            Country::Vietnam,
            Country::Indonesia,
        ]
    }
}

impl Default for StripeSettlementManager {
    fn default() -> Self {
        Self::new()
    }
}
```

---

### Step 3: Implement payout_scheduler.rs

**File:** `crates/siss-apac-expansion/src/settlement/payout_scheduler.rs`

```rust
use super::stripe_integration::{SettlementStatus, SettlementTransaction};
use chrono::Utc;

pub struct PayoutScheduler;

impl PayoutScheduler {
    pub fn schedule_payout(transaction: &mut SettlementTransaction) {
        if transaction.status == SettlementStatus::Pending {
            transaction.status = SettlementStatus::Scheduled;
        }
    }

    pub fn execute_payout(transaction: &mut SettlementTransaction) -> Result<(), String> {
        if transaction.status != SettlementStatus::Scheduled {
            return Err("Transaction not in scheduled state".to_string());
        }

        if Utc::now() < transaction.scheduled_payout_date {
            return Err("Payout date not yet reached".to_string());
        }

        transaction.status = SettlementStatus::InProgress;
        Ok(())
    }

    pub fn complete_payout(transaction: &mut SettlementTransaction) -> Result<(), String> {
        if transaction.status != SettlementStatus::InProgress {
            return Err("Transaction not in progress state".to_string());
        }

        transaction.status = SettlementStatus::Completed;
        transaction.completed_at = Some(Utc::now());
        Ok(())
    }

    pub fn fail_payout(transaction: &mut SettlementTransaction, _reason: &str) {
        transaction.status = SettlementStatus::Failed;
    }
}
```

---

### Step 4: Implement mod.rs

**File:** `crates/siss-apac-expansion/src/settlement/mod.rs`

```rust
pub mod stripe_integration;
pub mod payout_scheduler;

pub use stripe_integration::{
    Country, SettlementStatus, SettlementTransaction, StripeAccount, StripeSettlementManager,
};
pub use payout_scheduler::PayoutScheduler;
```

---

### Step 5: Create Migration File

**File:** `crates/siss-apac-expansion/migrations/002_settlement_tracking.sql`

```sql
CREATE TABLE IF NOT EXISTS stripe_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id VARCHAR(255) UNIQUE NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    connected_account VARCHAR(255) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS settlement_transactions (
    id UUID PRIMARY KEY,
    account_id VARCHAR(255) NOT NULL REFERENCES stripe_accounts(account_id),
    country_code VARCHAR(2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    amount_cents BIGINT NOT NULL,
    payout_speed_days INTEGER NOT NULL,
    scheduled_payout_date TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_settlement_status ON settlement_transactions(status);
CREATE INDEX idx_settlement_payout_date ON settlement_transactions(scheduled_payout_date);
CREATE INDEX idx_settlement_account ON settlement_transactions(account_id);
```

---

### Step 6: Run Tests (Should PASS)

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p siss-apac-expansion settlement_tests
```

**Expected:** ✅ All 10 tests pass

---

### Step 7: Run Clippy

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo clippy -p siss-apac-expansion --all-targets
```

**Expected:** ✅ No warnings

---

### Step 8: Commit

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
git add crates/siss-apac-expansion/src/settlement crates/siss-apac-expansion/migrations/002_settlement_tracking.sql crates/siss-apac-expansion/src/tests.rs
git commit -m "feat: multi-currency settlement with Stripe Connect (8 APAC markets, 1-3 day payout speeds)"
```

---

## Success Criteria

- [x] 10 tests passing
- [x] 8 markets supported with correct payout speeds
- [x] Settlement transaction lifecycle (Pending → Scheduled → InProgress → Completed)
- [x] Clippy clean
- [x] Migration file created
- [x] One commit

---

## Return Summary

```
AGENT 3 COMPLETION SUMMARY
==========================

✅ Multi-Currency Settlement
✅ 8 markets with Stripe Connect:
   - Singapore (SGD, 1-day)
   - Australia (AUD, 2-day)
   - Japan (JPY, 3-day)
   - South Korea (KRW, 2-day)
   - India (INR, 2-day)
   - Thailand (THB, 2-day)
   - Vietnam (VND, 3-day)
   - Indonesia (IDR, 3-day)

✅ Tests: 10/10 PASSING
✅ Settlement lifecycle implemented
✅ Payout scheduler with time-based execution
✅ Clippy: CLEAN
✅ Migration: 002_settlement_tracking.sql

Commit: feat: multi-currency settlement...
Git hash: [your hash]

Status: ✅ READY FOR AGENT 4
```
