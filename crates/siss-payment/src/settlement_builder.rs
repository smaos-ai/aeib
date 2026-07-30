use uuid::Uuid;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SettlementLeg {
    pub id: Uuid,
    pub from_currency: String,
    pub to_currency: String,
    pub amount_cents: i64,
    pub status: String,
}

#[derive(Debug)]
pub struct SettlementBuilder {
    legs: Vec<SettlementLeg>,
}

impl SettlementBuilder {
    pub fn new() -> Self {
        SettlementBuilder { legs: Vec::new() }
    }

    pub fn add_leg(
        mut self,
        from_currency: String,
        to_currency: String,
        amount_cents: i64,
    ) -> Self {
        let leg = SettlementLeg {
            id: Uuid::new_v4(),
            from_currency,
            to_currency,
            amount_cents,
            status: "pending".to_string(),
        };
        self.legs.push(leg);
        self
    }

    pub fn add_leg_object(mut self, leg: SettlementLeg) -> Self {
        self.legs.push(leg);
        self
    }

    pub fn get_legs(&self) -> &[SettlementLeg] {
        &self.legs
    }

    pub fn finalize(self) -> Result<crate::atomic_settlement::AtomicSettlement, String> {
        if self.legs.is_empty() {
            return Err("No legs in settlement".to_string());
        }

        // Validate all legs have positive amounts
        for leg in &self.legs {
            if leg.amount_cents <= 0 {
                return Err(format!("Negative amount in leg {}", leg.id));
            }
        }

        crate::atomic_settlement::AtomicSettlement::new(self.legs)
    }
}

impl Default for SettlementBuilder {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_builder_add_leg() {
        let settlement = SettlementBuilder::new()
            .add_leg("EUR".to_string(), "USD".to_string(), 10000)
            .add_leg("GBP".to_string(), "JPY".to_string(), 5000);

        assert_eq!(settlement.get_legs().len(), 2);
    }

    #[test]
    fn test_builder_empty_settlement() {
        let result = SettlementBuilder::new().finalize();
        assert!(result.is_err());
    }

    #[test]
    fn test_builder_negative_amount_rejected() {
        let result = SettlementBuilder::new()
            .add_leg("EUR".to_string(), "USD".to_string(), -10000)
            .finalize();

        assert!(result.is_err());
    }
}
