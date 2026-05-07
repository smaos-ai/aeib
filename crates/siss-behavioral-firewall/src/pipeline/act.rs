use sqlx::PgPool;
use uuid::Uuid;

use crate::types::{FirewallError, Verdict, Violation};

pub async fn act_on_verdict(
    pool: &PgPool,
    task_id: Uuid,
    persona_id: Uuid,
    tenant_id: Uuid,
    verdict: &Verdict,
    violations: &[Violation],
) -> Result<(), FirewallError> {
    for violation in violations {
        let _ = siss_graph_db::repo::edge_repo::insert_edge(
            pool,
            task_id,
            task_id,
            "violated_by",
            tenant_id,
            serde_json::json!({
                "checker": violation.checker,
                "severity": format!("{:?}", violation.severity),
                "message": violation.message,
            }),
        )
        .await;
    }

    match verdict {
        Verdict::Clear => {}
        Verdict::Blocked => {}
        Verdict::CriticalBlocked => {
            let _ = siss_graph_db::repo::node_repo::freeze_persona(pool, persona_id).await;
            let _ = siss_graph_db::repo::node_repo::update_task_status(pool, task_id, "failed").await;
        }
    }

    Ok(())
}
