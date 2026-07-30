use super::{
    DenyReason, PolicyAction, PolicyResource, ReBACError, RelationType, Relationship,
    SovereignIdentity,
};
use chrono::{DateTime, Utc};
use sqlx::{Row, postgres::PgPool};
use std::time::SystemTime;
use uuid::Uuid;

pub struct ReBAC_PG {
    pool: PgPool,
}

impl ReBAC_PG {
    pub async fn new(pool: PgPool) -> Self {
        ReBAC_PG { pool }
    }

    pub async fn grant_relationship(
        &self,
        from: SovereignIdentity,
        to: PolicyResource,
        rel_type: RelationType,
        expires_at: Option<SystemTime>,
    ) -> Result<Uuid, ReBACError> {
        let rel_id = Uuid::new_v4();
        let rel_type_str = format!("{:?}", rel_type);
        let (resource_type, resource_id) = resource_parts(&to);

        let expires_ts: Option<DateTime<Utc>> = expires_at.map(|st| st.into());

        sqlx::query(
            r#"
            INSERT INTO relationships (id, from_sovereign, to_resource_type, to_resource_id, relationship_type, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            "#,
        )
        .bind(rel_id)
        .bind(from.0)
        .bind(&resource_type)
        .bind(resource_id)
        .bind(&rel_type_str)
        .bind(expires_ts)
        .execute(&self.pool)
        .await
        .map_err(|e| ReBACError::Database(e.to_string()))?;

        Ok(rel_id)
    }

    pub async fn revoke_relationship(&self, rel_id: Uuid) -> Result<(), ReBACError> {
        let rows_affected = sqlx::query(
            "UPDATE relationships SET revoked_at = NOW() WHERE id = $1 AND revoked_at IS NULL",
        )
        .bind(rel_id)
        .execute(&self.pool)
        .await
        .map_err(|e| ReBACError::Database(e.to_string()))?
        .rows_affected();

        if rows_affected == 0 {
            return Err(ReBACError::NotFound);
        }

        Ok(())
    }

    pub async fn verify_relationship(
        &self,
        from: SovereignIdentity,
        to: PolicyResource,
        action: PolicyAction,
    ) -> Result<String, DenyReason> {
        let (resource_type, resource_id) = resource_parts(&to);

        let rows: Vec<(String,)> = sqlx::query_as(
            r#"
            SELECT relationship_type FROM relationships
            WHERE from_sovereign = $1
              AND to_resource_type = $2
              AND to_resource_id = $3
              AND revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at > NOW())
            "#,
        )
        .bind(from.0)
        .bind(&resource_type)
        .bind(resource_id)
        .fetch_all(&self.pool)
        .await
        .map_err(|e| DenyReason::ReBAC(e.to_string()))?;

        for (rel_type_str,) in rows {
            let rel_type = match rel_type_str.as_str() {
                "Owner" => RelationType::Owner,
                "Operator" => RelationType::Operator,
                "Observer" => RelationType::Observer,
                "Delegate" => RelationType::Delegate,
                "Participant" => RelationType::Participant,
                "Initiator" => RelationType::Initiator,
                _ => continue,
            };

            if Self::action_allowed_for_relation(&action, rel_type) {
                return Ok(format!("{:?} permits {:?}", rel_type, action));
            }
        }

        Err(DenyReason::ReBAC(format!(
            "No valid relationship to perform {:?}",
            action
        )))
    }

    fn action_allowed_for_relation(action: &PolicyAction, rel_type: RelationType) -> bool {
        match (action, rel_type) {
            (_, RelationType::Owner) => true,
            (
                PolicyAction::Pause
                | PolicyAction::Resume
                | PolicyAction::Abort
                | PolicyAction::AssignTask
                | PolicyAction::CancelTask,
                RelationType::Operator,
            ) => true,
            (PolicyAction::ReadMetrics | PolicyAction::StreamEvents, RelationType::Observer) => {
                true
            }
            (PolicyAction::CreatePolicy | PolicyAction::UpdatePolicy, RelationType::Delegate) => {
                true
            }
            (PolicyAction::VoteConsent, RelationType::Participant) => true,
            (PolicyAction::CancelTask | PolicyAction::Abort, RelationType::Initiator) => true,
            _ => false,
        }
    }

    pub async fn list_relationships(
        &self,
        from: SovereignIdentity,
    ) -> Result<Vec<Relationship>, ReBACError> {
        let rows = sqlx::query(
            r#"
            SELECT id, from_sovereign, to_resource_type, to_resource_id, relationship_type, created_at, expires_at, revoked_at
            FROM relationships
            WHERE from_sovereign = $1
            "#,
        )
        .bind(from.0)
        .fetch_all(&self.pool)
        .await
        .map_err(|e| ReBACError::Database(e.to_string()))?;

        let mut relationships = Vec::new();
        for row in rows {
            let resource_type: String = row.get("to_resource_type");
            let resource_id: Uuid = row.get("to_resource_id");
            let to_resource = match resource_type.as_str() {
                "Agent" => PolicyResource::Agent(resource_id),
                "Task" => PolicyResource::Task(resource_id),
                "ConsentGrant" => PolicyResource::ConsentGrant(resource_id),
                "ArbitrationCycle" => PolicyResource::ArbitrationCycle(resource_id),
                "FeedbackChannel" => PolicyResource::FeedbackChannel(resource_id),
                _ => continue,
            };

            let rel_type_str: String = row.get("relationship_type");
            let rel_type = match rel_type_str.as_str() {
                "Owner" => RelationType::Owner,
                "Operator" => RelationType::Operator,
                "Observer" => RelationType::Observer,
                "Delegate" => RelationType::Delegate,
                "Participant" => RelationType::Participant,
                "Initiator" => RelationType::Initiator,
                _ => continue,
            };

            let created_ts: DateTime<Utc> = row.get("created_at");
            let expires_ts: Option<DateTime<Utc>> = row.get("expires_at");
            let revoked_ts: Option<DateTime<Utc>> = row.get("revoked_at");

            relationships.push(Relationship {
                id: row.get("id"),
                from: SovereignIdentity(row.get("from_sovereign")),
                to_resource,
                rel_type,
                created_at: created_ts.into(),
                expires_at: expires_ts.map(|dt| dt.into()),
                revoked_at: revoked_ts.map(|dt| dt.into()),
            });
        }

        Ok(relationships)
    }

    pub async fn detect_cycle(
        &self,
        from: &SovereignIdentity,
        to: &SovereignIdentity,
    ) -> Result<(), ReBACError> {
        // Iterative BFS for cycle detection (depth limit 3)
        use std::collections::VecDeque;

        let mut queue = VecDeque::new();
        let mut visited = std::collections::HashSet::new();

        queue.push_back((*from, 0));
        visited.insert(*from);

        while let Some((current, depth)) = queue.pop_front() {
            if depth > 3 {
                return Err(ReBACError::MaxDepthExceeded);
            }

            let rels = self.list_relationships(current).await?;
            for rel in rels {
                if rel.rel_type == RelationType::Delegate {
                    if let PolicyResource::Agent(agent_id) = rel.to_resource {
                        let next = SovereignIdentity(agent_id);

                        if next == *to && depth + 1 > 3 {
                            return Err(ReBACError::MaxDepthExceeded);
                        }

                        if visited.contains(&next) {
                            return Err(ReBACError::CycleDetected);
                        }

                        visited.insert(next);
                        queue.push_back((next, depth + 1));
                    }
                }
            }
        }

        Ok(())
    }
}

fn resource_parts(resource: &PolicyResource) -> (String, Uuid) {
    match resource {
        PolicyResource::Agent(id) => ("Agent".to_string(), *id),
        PolicyResource::Task(id) => ("Task".to_string(), *id),
        PolicyResource::ConsentGrant(id) => ("ConsentGrant".to_string(), *id),
        PolicyResource::ArbitrationCycle(id) => ("ArbitrationCycle".to_string(), *id),
        PolicyResource::FeedbackChannel(id) => ("FeedbackChannel".to_string(), *id),
    }
}
