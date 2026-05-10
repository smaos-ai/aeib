use sqlx::{PgPool, Row};
use uuid::Uuid;

/// A governance rule row from the database.
#[derive(Debug)]
pub struct GovernanceRuleRow {
    pub id: Uuid,
    pub name: String,
    pub rule_type: String,
    pub expression: String,
    pub severity: String,
    pub applies_to: Vec<String>,
}

/// Find all active governance rules that apply to a given node type.
pub async fn find_active_rules(
    pool: &PgPool,
    node_type: &str,
    tenant_id: Uuid,
) -> Result<Vec<GovernanceRuleRow>, sqlx::Error> {
    let rows = sqlx::query(
        "SELECT id, name, rule_type::text, expression, severity::text, applies_to \
         FROM governance_rules \
         WHERE is_active = TRUE AND tenant_id = $1 AND $2 = ANY(applies_to)",
    )
    .bind(tenant_id)
    .bind(node_type)
    .fetch_all(pool)
    .await?;

    Ok(rows
        .into_iter()
        .map(|row| GovernanceRuleRow {
            id: row.get("id"),
            name: row.get("name"),
            rule_type: row.get("rule_type"),
            expression: row.get("expression"),
            severity: row.get("severity"),
            applies_to: row.get("applies_to"),
        })
        .collect())
}

/// Log a governance rule violation by creating a VIOLATED_BY edge.
pub async fn log_violation(
    pool: &PgPool,
    rule_id: Uuid,
    violating_entity_id: Uuid,
    tenant_id: Uuid,
) -> Result<Uuid, sqlx::Error> {
    let edge_id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO edges (id, source_id, target_id, edge_type, tenant_id, metadata) \
         VALUES ($1, $2, $3, 'violated_by'::edge_type, $4, $5)",
    )
    .bind(edge_id)
    .bind(rule_id)
    .bind(violating_entity_id)
    .bind(tenant_id)
    .bind(serde_json::json!({"violated_at": chrono::Utc::now().to_rfc3339()}))
    .execute(pool)
    .await?;
    Ok(edge_id)
}
