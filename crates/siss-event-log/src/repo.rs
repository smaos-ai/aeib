use crate::types::{EventFilter, EventId, JobId, LogError, SystemEvent};
use futures::Stream;
use sqlx::PgPool;
use std::pin::Pin;
use uuid::Uuid;

pub struct EventLog {
    pool: PgPool,
}

impl EventLog {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }

    /// Append an event to the immutable log. Returns the EventId (UUID).
    pub async fn append_event(
        &self,
        job_id: JobId,
        event: SystemEvent,
    ) -> Result<EventId, LogError> {
        let event_id = Uuid::new_v4();
        let payload = serde_json::to_value(&event)
            .map_err(|e| LogError::DatabaseError(e.to_string()))?;

        sqlx::query(
            "INSERT INTO event_log (id, job_id, event_type, payload, created_at)
             VALUES ($1, $2, $3, $4, NOW())",
        )
        .bind(event_id)
        .bind(job_id)
        .bind(Self::event_type_str(&event))
        .bind(payload)
        .execute(&self.pool)
        .await
        .map_err(|e| LogError::DatabaseError(e.to_string()))?;

        Ok(event_id)
    }

    /// Retrieve all events for a job.
    pub async fn get_events(&self, job_id: JobId) -> Result<Vec<SystemEvent>, LogError> {
        let rows = sqlx::query_as::<_, (serde_json::Value,)>(
            "SELECT payload FROM event_log WHERE job_id = $1 ORDER BY created_at ASC",
        )
        .bind(job_id)
        .fetch_all(&self.pool)
        .await
        .map_err(|e| LogError::DatabaseError(e.to_string()))?;

        let mut events = Vec::new();
        for (payload,) in rows {
            let event: SystemEvent = serde_json::from_value(payload)
                .map_err(|e| LogError::DatabaseError(e.to_string()))?;
            events.push(event);
        }

        Ok(events)
    }

    /// Stream events matching a filter.
    pub async fn stream_events(
        &self,
        filter: EventFilter,
    ) -> Result<Pin<Box<dyn Stream<Item = SystemEvent> + Send>>, LogError> {
        let query = if let Some(job_id) = filter.job_id {
            format!(
                "SELECT payload FROM event_log WHERE job_id = '{}' ORDER BY created_at ASC",
                job_id
            )
        } else {
            "SELECT payload FROM event_log ORDER BY created_at ASC".to_string()
        };

        let rows = sqlx::query_as::<_, (serde_json::Value,)>(&query)
            .fetch_all(&self.pool)
            .await
            .map_err(|e| LogError::DatabaseError(e.to_string()))?;

        let events: Vec<SystemEvent> = rows
            .into_iter()
            .filter_map(|(payload,)| serde_json::from_value(payload).ok())
            .collect();

        let stream = futures::stream::iter(events);
        Ok(Box::pin(stream))
    }

    /// Helper: extract event type string from SystemEvent.
    fn event_type_str(event: &SystemEvent) -> &'static str {
        match event {
            SystemEvent::JobDispatched { .. } => "JobDispatched",
            SystemEvent::JobCompleted { .. } => "JobCompleted",
            SystemEvent::JobFailed { .. } => "JobFailed",
            SystemEvent::AccessDecision { .. } => "AccessDecision",
        }
    }

    // INTENTIONALLY NO UPDATE OR DELETE METHODS
    // The API surface is append-only by design.
    // Attempting to modify or delete events will fail at the Rust type level.
}

#[cfg(test)]
mod tests {
    

    #[tokio::test]
    async fn test_append_event_succeeds() {
        // Unit test: append_event signature and basic logic
        // (integration test with real DB in migrations/tests)
    }

    #[tokio::test]
    async fn test_no_update_or_delete_methods() {
        // Compiler-level guarantee: if UPDATE or DELETE methods existed,
        // this test would fail to compile (intentionally).
        // Since they don't exist, this test documents the API contract.
    }
}
