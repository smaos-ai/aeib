pub struct PaymentRouter;

impl PaymentRouter {
    pub fn route_payment(amount_cents: i64) -> (i64, i64) {
        let platform_fee = (amount_cents + 99) / 100;
        let creator_payout = amount_cents - platform_fee;
        (platform_fee, creator_payout)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_router_splits_99_1() {
        let (platform, creator) = PaymentRouter::route_payment(10000);
        assert_eq!(platform, 100);
        assert_eq!(creator, 9900);
    }
}
