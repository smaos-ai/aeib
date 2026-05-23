use uuid::Uuid;

#[derive(Clone)]
pub struct PrepareRequest {
    pub capsule_id: Uuid,
    pub budget_limit: u64,
    pub budget_spent: u64,
    pub risk_class: u8,
}

#[derive(Clone)]
pub struct PrepareToken {
    pub capsule_id: Uuid,
    pub reservation_id: Uuid,
}

impl PrepareRequest {
    pub fn validate(&self) -> Result<PrepareToken, String> {
        if self.budget_spent >= self.budget_limit {
            return Err("Budget exceeded".to_string());
        }
        Ok(PrepareToken {
            capsule_id: self.capsule_id,
            reservation_id: Uuid::new_v4(),
        })
    }
}
