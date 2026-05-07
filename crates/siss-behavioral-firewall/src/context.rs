use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct InspectionContext {
    pub task_id: Uuid,
    pub token_cost: i64,
    pub output: serde_json::Value,
    pub authorized_tools: Vec<Uuid>,
    pub budget_remaining: i64,
}
