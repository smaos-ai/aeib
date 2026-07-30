use siss_graph_db::repo::cross_sovereign_delegation_repo;
use sqlx::PgPool;
use std::collections::{HashMap, VecDeque};
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct RoutingDecision {
    pub path: Vec<Uuid>,
    pub allowed: bool,
    pub ceiling_tier: u32,
    pub reason: String,
}

#[derive(Debug)]
pub enum RoutingError {
    CycleDetected { cycle_nodes: Vec<Uuid> },
    CeilingExceeded { requested: u32, allowed: u32 },
    NoPathFound,
    DepthLimitExceeded,
    Database(String),
}

impl From<sqlx::Error> for RoutingError {
    fn from(err: sqlx::Error) -> Self {
        RoutingError::Database(err.to_string())
    }
}

const MAX_DELEGATION_DEPTH: usize = 4;

/// Route a delegation request from source to target sovereign using BFS.
///
/// Algorithm:
/// 1. BFS from source toward target checking active grants
/// 2. Track path and minimum ceiling across hops
/// 3. Check depth limit (max 4 hops)
/// 4. Detect cycles by checking if path forms a loop
/// 5. Return RoutingDecision or RoutingError
pub async fn route_request(
    pool: &PgPool,
    source_sovereign: Uuid,
    target_sovereign: Uuid,
    required_tier: u32,
) -> Result<RoutingDecision, RoutingError> {
    if source_sovereign == target_sovereign {
        return Ok(RoutingDecision {
            path: vec![source_sovereign],
            allowed: true,
            ceiling_tier: u32::MAX,
            reason: "Same sovereign".to_string(),
        });
    }

    // BFS to find path
    let mut queue = VecDeque::new();
    let mut visited = std::collections::HashSet::new();
    let mut parent_map: HashMap<Uuid, (Uuid, u32)> = HashMap::new();

    queue.push_back(source_sovereign);
    visited.insert(source_sovereign);

    let mut found_target = false;

    while let Some(current) = queue.pop_front() {
        if current == target_sovereign {
            found_target = true;
            break;
        }

        // Get active grants from current sovereign
        let grants = cross_sovereign_delegation_repo::list_active_grants_for_grantor(pool, current)
            .await
            .map_err(|e| RoutingError::Database(e.to_string()))?;

        for grant in grants {
            if !visited.contains(&grant.grantee_sovereign_id) {
                visited.insert(grant.grantee_sovereign_id);
                parent_map.insert(
                    grant.grantee_sovereign_id,
                    (current, grant.ceiling_tier as u32),
                );

                // Check depth limit
                let depth = calculate_path_depth(&parent_map, grant.grantee_sovereign_id);
                if depth > MAX_DELEGATION_DEPTH {
                    return Err(RoutingError::DepthLimitExceeded);
                }

                queue.push_back(grant.grantee_sovereign_id);
            }
        }
    }

    if !found_target {
        return Err(RoutingError::NoPathFound);
    }

    // Reconstruct path
    let mut path = vec![target_sovereign];
    let mut current = target_sovereign;

    while current != source_sovereign {
        if let Some((parent, _)) = parent_map.get(&current) {
            path.push(*parent);
            current = *parent;
        } else {
            return Err(RoutingError::NoPathFound);
        }
    }

    path.reverse();

    // Detect cycles (check if path contains duplicates)
    if path.iter().collect::<std::collections::HashSet<_>>().len() != path.len() {
        return Err(RoutingError::CycleDetected {
            cycle_nodes: path.clone(),
        });
    }

    // Calculate minimum ceiling across path
    let mut min_ceiling = u32::MAX;
    for i in 0..path.len() - 1 {
        if let Some((_, ceiling)) = parent_map.get(&path[i + 1]) {
            min_ceiling = min_ceiling.min(*ceiling);
        }
    }

    // Check ceiling constraint
    if required_tier > min_ceiling {
        return Err(RoutingError::CeilingExceeded {
            requested: required_tier,
            allowed: min_ceiling,
        });
    }

    Ok(RoutingDecision {
        path,
        allowed: true,
        ceiling_tier: min_ceiling,
        reason: "Delegation path found and authorized".to_string(),
    })
}

fn calculate_path_depth(
    parent_map: &std::collections::HashMap<Uuid, (Uuid, u32)>,
    mut current: Uuid,
) -> usize {
    let mut depth = 1;
    while let Some((parent, _)) = parent_map.get(&current) {
        depth += 1;
        current = *parent;
    }
    depth
}
