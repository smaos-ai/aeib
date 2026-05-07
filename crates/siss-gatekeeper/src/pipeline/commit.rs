use chrono::Utc;
use sqlx::PgPool;
use uuid::Uuid;

use crate::payload::build_signing_payload;
use crate::signer::Signer;
use crate::types::{AuthorizationResult, GatekeeperError};
use siss_graph_core::node::NodeId;

/// Pipeline Step 5: Sign the PaymentMandate, persist edges, transition Task.
#[allow(clippy::too_many_arguments)]
pub async fn sign_and_commit(
    pool: &PgPool,
    signer: &dyn Signer,
    task_id: Uuid,
    persona_id: Uuid,
    intent_mandate_id: Uuid,
    estimated_cost: i64,
    risk_class: &str,
    tenant_id: Uuid,
) -> Result<AuthorizationResult, GatekeeperError> {
    let now = Utc::now();
    let timestamp_secs = now.timestamp();

    // Build and sign payload
    let payload = build_signing_payload(task_id, intent_mandate_id, estimated_cost, timestamp_secs);
    let signature = signer.sign(&payload).map_err(|e| GatekeeperError::SigningError {
        message: e.message,
    })?;

    // Create signed PaymentMandate
    let pm_id = siss_graph_db::repo::node_repo::insert_payment_mandate(
        pool,
        intent_mandate_id,
        estimated_cost,
        risk_class,
        &signature,
        tenant_id,
    )
    .await?;

    // Create edges
    // AUTHORIZED_BY: PaymentMandate → IntentMandate
    siss_graph_db::repo::edge_repo::insert_edge(
        pool, pm_id, intent_mandate_id, "authorized_by", tenant_id, serde_json::json!({}),
    )
    .await?;

    // GOVERNED_BY: Task → IntentMandate
    siss_graph_db::repo::edge_repo::insert_edge(
        pool, task_id, intent_mandate_id, "governed_by", tenant_id, serde_json::json!({}),
    )
    .await?;

    // INITIATED_BY: Task → Persona
    siss_graph_db::repo::edge_repo::insert_edge(
        pool, task_id, persona_id, "initiated_by", tenant_id, serde_json::json!({}),
    )
    .await?;

    // Transition Task: pending → authorized
    siss_graph_db::repo::node_repo::update_task_status(pool, task_id, "authorized")
        .await?;

    Ok(AuthorizationResult {
        task_id: NodeId(task_id),
        payment_mandate_id: NodeId(pm_id),
        signature,
        authorized_at: now,
    })
}
