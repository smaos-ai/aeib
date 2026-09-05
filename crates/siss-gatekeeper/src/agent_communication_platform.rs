use sqlx::PgPool;
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct RoutedMessage {
    pub id: Uuid,
    pub message_id: String,
    pub source_agent_id: String,
    pub target_agent_id: String,
    pub message: String,
    pub context_state: serde_json::Value,
    pub route_hops: i32,
}

/// Route stateful message from source to target with context preservation
pub async fn route_stateful_message(
    pool: &PgPool,
    source_agent_id: &str,
    target_agent_id: &str,
    message: String,
    context_state: serde_json::Value,
) -> Result<RoutedMessage, Box<dyn std::error::Error>> {
    let id = Uuid::new_v4();
    let message_id = format!("msg_{}", id);

    sqlx::query(
        "INSERT INTO acp_message_log (id, message_id, source_agent_id, target_agent_id, message_type, payload, context_state, route_hops, routed_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())"
    )
    .bind(id)
    .bind(&message_id)
    .bind(source_agent_id)
    .bind(target_agent_id)
    .bind("direct")
    .bind(serde_json::to_value(&message)?)
    .bind(&context_state)
    .bind(1)
    .execute(pool)
    .await?;

    Ok(RoutedMessage {
        id,
        message_id,
        source_agent_id: source_agent_id.to_string(),
        target_agent_id: target_agent_id.to_string(),
        message,
        context_state,
        route_hops: 1,
    })
}
