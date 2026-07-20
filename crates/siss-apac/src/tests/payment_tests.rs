#[cfg(test)]
mod tests {
    use crate::{PaymentProcessor, PaymentEngine, TransactionStatus};

    #[test]
    fn test_alipay_processor_config() {
        assert_eq!(PaymentProcessor::Alipay.provider_id(), "alipay");
        assert_eq!(PaymentProcessor::Alipay.settlement_cycle_days(), 1);
        assert_eq!(PaymentProcessor::Alipay.min_settlement_amount_cents(), 100);
        assert_eq!(PaymentProcessor::Alipay.fee_bps(), 25);
    }

    #[test]
    fn test_wechat_pay_processor_config() {
        assert_eq!(PaymentProcessor::WeChatPay.provider_id(), "wechat_pay");
        assert_eq!(PaymentProcessor::WeChatPay.settlement_cycle_days(), 1);
        assert_eq!(PaymentProcessor::WeChatPay.min_settlement_amount_cents(), 100);
        assert_eq!(PaymentProcessor::WeChatPay.fee_bps(), 30);
    }

    #[test]
    fn test_gcash_processor_config() {
        assert_eq!(PaymentProcessor::GCash.provider_id(), "gcash");
        assert_eq!(PaymentProcessor::GCash.settlement_cycle_days(), 2);
        assert_eq!(PaymentProcessor::GCash.min_settlement_amount_cents(), 5000);
        assert_eq!(PaymentProcessor::GCash.fee_bps(), 45);
    }

    #[test]
    fn test_paytm_processor_config() {
        assert_eq!(PaymentProcessor::Paytm.provider_id(), "paytm");
        assert_eq!(PaymentProcessor::Paytm.settlement_cycle_days(), 2);
        assert_eq!(PaymentProcessor::Paytm.min_settlement_amount_cents(), 10000);
        assert_eq!(PaymentProcessor::Paytm.fee_bps(), 50);
    }

    #[test]
    fn test_initiate_transaction_alipay() {
        let mut engine = PaymentEngine::new();
        let result = engine.initiate_transaction(
            PaymentProcessor::Alipay,
            1000,
            "CNY"
        );

        assert!(result.is_ok());
        let tx = result.unwrap();
        assert_eq!(tx.processor, PaymentProcessor::Alipay);
        assert_eq!(tx.amount_cents, 1000);
        assert_eq!(tx.currency, "CNY");
        assert_eq!(tx.status, TransactionStatus::Pending);
    }

    #[test]
    fn test_initiate_transaction_wechat_pay() {
        let mut engine = PaymentEngine::new();
        let result = engine.initiate_transaction(
            PaymentProcessor::WeChatPay,
            5000,
            "CNY"
        );

        assert!(result.is_ok());
        let tx = result.unwrap();
        assert_eq!(tx.processor, PaymentProcessor::WeChatPay);
        assert_eq!(tx.status, TransactionStatus::Pending);
    }

    #[test]
    fn test_initiate_transaction_gcash() {
        let mut engine = PaymentEngine::new();
        let result = engine.initiate_transaction(
            PaymentProcessor::GCash,
            10000,
            "PHP"
        );

        assert!(result.is_ok());
        let tx = result.unwrap();
        assert_eq!(tx.processor, PaymentProcessor::GCash);
        assert_eq!(tx.currency, "PHP");
    }

    #[test]
    fn test_initiate_transaction_paytm() {
        let mut engine = PaymentEngine::new();
        let result = engine.initiate_transaction(
            PaymentProcessor::Paytm,
            50000,
            "INR"
        );

        assert!(result.is_ok());
        let tx = result.unwrap();
        assert_eq!(tx.processor, PaymentProcessor::Paytm);
        assert_eq!(tx.currency, "INR");
    }

    #[test]
    fn test_transaction_below_minimum_fails() {
        let mut engine = PaymentEngine::new();
        let result = engine.initiate_transaction(
            PaymentProcessor::Alipay,
            50,
            "CNY"
        );

        assert!(result.is_err());
    }

    #[test]
    fn test_complete_transaction() {
        let mut engine = PaymentEngine::new();
        let tx = engine.initiate_transaction(
            PaymentProcessor::Alipay,
            1000,
            "CNY"
        ).unwrap();

        let result = engine.complete_transaction(&tx.id);
        assert!(result.is_ok());
        assert_eq!(result.unwrap().status, TransactionStatus::Completed);
    }

    #[test]
    fn test_calculate_settlement_fee_alipay() {
        let engine = PaymentEngine::new();
        let fee = engine.calculate_settlement_fee(PaymentProcessor::Alipay, 10000);
        assert_eq!(fee, 25); // 10000 * 0.25% / 100
    }

    #[test]
    fn test_calculate_settlement_fee_paytm() {
        let engine = PaymentEngine::new();
        let fee = engine.calculate_settlement_fee(PaymentProcessor::Paytm, 10000);
        assert_eq!(fee, 50); // 10000 * 0.50% / 100
    }

    #[test]
    fn test_process_settlement() {
        let mut engine = PaymentEngine::new();
        let tx = engine.initiate_transaction(
            PaymentProcessor::Alipay,
            1000,
            "CNY"
        ).unwrap();

        engine.complete_transaction(&tx.id).unwrap();
        let result = engine.process_settlement(&tx.id);

        assert!(result.is_ok());
        let settled_tx = engine.get_transaction(&tx.id).unwrap();
        assert_eq!(settled_tx.status, TransactionStatus::Settled);
        assert!(settled_tx.settled_at.is_some());
    }

    #[test]
    fn test_get_pending_settlements() {
        let mut engine = PaymentEngine::new();
        let tx1 = engine.initiate_transaction(
            PaymentProcessor::Alipay,
            1000,
            "CNY"
        ).unwrap();
        let tx2 = engine.initiate_transaction(
            PaymentProcessor::GCash,
            10000,
            "PHP"
        ).unwrap();

        engine.complete_transaction(&tx1.id).unwrap();
        engine.complete_transaction(&tx2.id).unwrap();

        let pending = engine.get_pending_settlements();
        assert_eq!(pending.len(), 2);
    }

    #[test]
    fn test_settlement_status() {
        let mut engine = PaymentEngine::new();
        let tx = engine.initiate_transaction(
            PaymentProcessor::Alipay,
            1000,
            "CNY"
        ).unwrap();

        assert_eq!(engine.settlement_status(&tx.id), Some(TransactionStatus::Pending));
        engine.complete_transaction(&tx.id).unwrap();
        assert_eq!(engine.settlement_status(&tx.id), Some(TransactionStatus::Completed));
    }
}
