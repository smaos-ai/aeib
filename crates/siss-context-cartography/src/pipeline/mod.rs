pub mod validate;
pub mod session;
pub mod record;

use sqlx::PgPool;

use siss_graph_core::node::NodeId;

use crate::budget::apply_budget;
use crate::config::RetrievalConfig;
use crate::retrieval;
use crate::types::{CartographyError, CartographyRequest, VisibleField};

/// The sole entry point for building the Visible Field.
pub async fn build_context(
    pool: &PgPool,
    request: &CartographyRequest,
    config: &RetrievalConfig,
) -> Result<VisibleField, CartographyError> {
    let task_id = request.task_id.0;
    let persona_id = request.persona_id.0;
    let tenant_id = request.tenant_id.0;

    // Step 1: Validate
    validate::validate(pool, task_id, persona_id, tenant_id).await?;

    // Step 2: Create Session
    let session_id = session::create_session(
        pool, task_id, persona_id, tenant_id, request.token_budget,
    )
    .await?;

    // Step 3: Retrieve memories
    let (procedural, semantic, episodic) = retrieval::retrieve_all_tiers(
        pool, persona_id, tenant_id, config,
    )
    .await?;

    // Step 4: Apply token budget
    let (proc_trimmed, sem_trimmed, epi_trimmed, total_tokens) = apply_budget(
        procedural, semantic, episodic, request.token_budget, config.tokens_per_char,
    );

    // Build VisibleField
    let field = VisibleField {
        session_id: NodeId(session_id),
        procedural: proc_trimmed,
        semantic: sem_trimmed,
        episodic: epi_trimmed,
        total_tokens_estimated: total_tokens,
    };

    // Step 5: Record
    record::record_visible_field(pool, session_id, tenant_id, &field).await?;

    Ok(field)
}
