use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum PaymentProcessor {
    Alipay,
    WeChatPay,
    GCash,
    Paytm,
}

impl PaymentProcessor {
    pub fn provider_id(&self) -> &'static str {
        match self {
            PaymentProcessor::Alipay => "alipay",
            PaymentProcessor::WeChatPay => "wechat_pay",
            PaymentProcessor::GCash => "gcash",
            PaymentProcessor::Paytm => "paytm",
        }
    }

    pub fn settlement_cycle_days(&self) -> u32 {
        match self {
            PaymentProcessor::Alipay => 1,
            PaymentProcessor::WeChatPay => 1,
            PaymentProcessor::GCash => 2,
            PaymentProcessor::Paytm => 2,
        }
    }

    pub fn min_settlement_amount_cents(&self) -> u64 {
        match self {
            PaymentProcessor::Alipay => 100,    // 1 CNY
            PaymentProcessor::WeChatPay => 100, // 1 CNY
            PaymentProcessor::GCash => 5000,    // 50 PHP
            PaymentProcessor::Paytm => 10000,   // 100 INR
        }
    }

    pub fn fee_bps(&self) -> u16 {
        match self {
            PaymentProcessor::Alipay => 25,    // 0.25%
            PaymentProcessor::WeChatPay => 30, // 0.30%
            PaymentProcessor::GCash => 45,     // 0.45%
            PaymentProcessor::Paytm => 50,     // 0.50%
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    pub id: String,
    pub processor: PaymentProcessor,
    pub amount_cents: u64,
    pub currency: String,
    pub status: TransactionStatus,
    pub created_at: i64,
    pub settled_at: Option<i64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TransactionStatus {
    Pending,
    Completed,
    Failed,
    Settled,
}

pub struct PaymentEngine {
    transactions: HashMap<String, Transaction>,
    settlement_queue: Vec<String>,
}

impl PaymentEngine {
    pub fn new() -> Self {
        PaymentEngine {
            transactions: HashMap::new(),
            settlement_queue: Vec::new(),
        }
    }

    pub fn initiate_transaction(
        &mut self,
        processor: PaymentProcessor,
        amount_cents: u64,
        currency: &str,
    ) -> crate::Result<Transaction> {
        if amount_cents < processor.min_settlement_amount_cents() {
            return Err(crate::ApacError::PaymentError(format!(
                "Amount {} cents below minimum {} for {}",
                amount_cents,
                processor.min_settlement_amount_cents(),
                processor.provider_id()
            )));
        }

        let tx = Transaction {
            id: format!("txn_{}", Uuid::new_v4()),
            processor,
            amount_cents,
            currency: currency.to_string(),
            status: TransactionStatus::Pending,
            created_at: chrono::Utc::now().timestamp(),
            settled_at: None,
        };

        self.transactions.insert(tx.id.clone(), tx.clone());
        Ok(tx)
    }

    pub fn complete_transaction(&mut self, tx_id: &str) -> crate::Result<Transaction> {
        let tx = self.transactions.get_mut(tx_id).ok_or_else(|| {
            crate::ApacError::PaymentError(format!("Transaction not found: {}", tx_id))
        })?;

        tx.status = TransactionStatus::Completed;
        self.settlement_queue.push(tx_id.to_string());
        Ok(tx.clone())
    }

    pub fn get_transaction(&self, tx_id: &str) -> Option<Transaction> {
        self.transactions.get(tx_id).cloned()
    }

    pub fn calculate_settlement_fee(&self, processor: PaymentProcessor, amount_cents: u64) -> u64 {
        (amount_cents as u128 * processor.fee_bps() as u128 / 10000) as u64
    }

    pub fn process_settlement(&mut self, tx_id: &str) -> crate::Result<()> {
        let tx = self.transactions.get_mut(tx_id).ok_or_else(|| {
            crate::ApacError::PaymentError(format!("Transaction not found: {}", tx_id))
        })?;

        if tx.status != TransactionStatus::Completed {
            return Err(crate::ApacError::PaymentError(
                "Transaction must be completed before settlement".to_string(),
            ));
        }

        tx.status = TransactionStatus::Settled;
        tx.settled_at = Some(chrono::Utc::now().timestamp());
        Ok(())
    }

    pub fn get_pending_settlements(&self) -> Vec<Transaction> {
        self.settlement_queue
            .iter()
            .filter_map(|id| {
                self.transactions
                    .get(id)
                    .filter(|tx| tx.status == TransactionStatus::Completed)
                    .cloned()
            })
            .collect()
    }

    pub fn settlement_status(&self, tx_id: &str) -> Option<TransactionStatus> {
        self.transactions.get(tx_id).map(|tx| tx.status)
    }
}

impl Default for PaymentEngine {
    fn default() -> Self {
        Self::new()
    }
}
