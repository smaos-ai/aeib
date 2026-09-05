use sqlx::PgPool;
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct DelegationChain {
    pub sovereigns: Vec<Uuid>,
    pub ceiling_tiers: Vec<String>,
}

#[derive(Debug, Clone)]
pub enum ValidationError {
    InvalidChain,
    CycleDetected,
    DatabaseError(String),
    NotFound,
}

pub async fn verify_transitive_chain(
    pool: &PgPool,
    chain: &DelegationChain,
) -> Result<bool, ValidationError> {
    if chain.sovereigns.is_empty() {
        return Err(ValidationError::InvalidChain);
    }

    // Check for cycles
    let mut seen = std::collections::HashSet::new();
    for sovereign in &chain.sovereigns {
        if !seen.insert(sovereign) {
            return Err(ValidationError::CycleDetected);
        }
    }

    // Verify each delegation exists in database
    for window in chain.sovereigns.windows(2) {
        let from_sovereign = window[0];
        let to_sovereign = window[1];

        let exists: bool = sqlx::query_scalar(
            r#"
            SELECT EXISTS(
                SELECT 1 FROM delegation_relationships
                WHERE delegator = $1 AND delegatee = $2
            )
            "#,
        )
        .bind(from_sovereign)
        .bind(to_sovereign)
        .fetch_one(pool)
        .await
        .map_err(|e| ValidationError::DatabaseError(e.to_string()))?;

        if !exists {
            return Err(ValidationError::InvalidChain);
        }
    }

    Ok(true)
}

pub async fn extend_chain(
    pool: &PgPool,
    existing_chain: &DelegationChain,
    next_sovereign: Uuid,
    next_ceiling: &str,
) -> Result<DelegationChain, ValidationError> {
    // Verify no cycle would be created
    let mut new_sovereigns = existing_chain.sovereigns.clone();
    if new_sovereigns.contains(&next_sovereign) {
        return Err(ValidationError::CycleDetected);
    }

    // Verify delegation exists
    if let Some(&last_sovereign) = new_sovereigns.last() {
        let exists: bool = sqlx::query_scalar(
            r#"
            SELECT EXISTS(
                SELECT 1 FROM delegation_relationships
                WHERE delegator = $1 AND delegatee = $2
            )
            "#,
        )
        .bind(last_sovereign)
        .bind(next_sovereign)
        .fetch_one(pool)
        .await
        .map_err(|e| ValidationError::DatabaseError(e.to_string()))?;

        if !exists {
            return Err(ValidationError::InvalidChain);
        }
    }

    new_sovereigns.push(next_sovereign);
    let mut new_ceilings = existing_chain.ceiling_tiers.clone();
    new_ceilings.push(next_ceiling.to_string());

    // Compute the lowest ceiling
    let effective_ceiling = compute_lowest_ceiling(&new_ceilings);
    // Keep only the effective ceiling
    new_ceilings = vec![effective_ceiling];

    Ok(DelegationChain {
        sovereigns: new_sovereigns,
        ceiling_tiers: new_ceilings,
    })
}

pub async fn get_shortest_path(
    pool: &PgPool,
    source_sovereign: Uuid,
    target_sovereign: Uuid,
) -> Result<Option<DelegationChain>, sqlx::Error> {
    // Query for direct delegation first
    let direct: Option<String> = sqlx::query_scalar(
        r#"
        SELECT ceiling_tier FROM delegation_relationships
        WHERE delegator = $1 AND delegatee = $2 LIMIT 1
        "#,
    )
    .bind(source_sovereign)
    .bind(target_sovereign)
    .fetch_optional(pool)
    .await?;

    if let Some(ceiling) = direct {
        return Ok(Some(DelegationChain {
            sovereigns: vec![source_sovereign, target_sovereign],
            ceiling_tiers: vec![ceiling],
        }));
    }

    // TODO: Implement BFS for longer paths
    Ok(None)
}

fn compute_lowest_ceiling(ceilings: &[String]) -> String {
    // Simple tier ordering: TIER_1 < TIER_2 < TIER_3 < TIER_4
    if ceilings.is_empty() {
        return "TIER_4".to_string();
    }

    let tier_order = |tier: &str| -> i32 {
        match tier {
            "TIER_1" => 1,
            "TIER_2" => 2,
            "TIER_3" => 3,
            "TIER_4" => 4,
            _ => 4,
        }
    };

    let mut lowest = ceilings[0].clone();
    for ceiling in ceilings.iter().skip(1) {
        if tier_order(ceiling) < tier_order(&lowest) {
            lowest = ceiling.clone();
        }
    }

    lowest
}
