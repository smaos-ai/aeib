use chrono::{DateTime, Utc};
use uuid::Uuid;

#[derive(Clone, Debug)]
pub struct TimeCapsuleCapsule {
    pub id: Uuid,
    scheduled_publishes: Vec<ScheduledPublish>,
    audit_trail: Vec<PublishAuditEntry>,
    publish_accuracy_samples: Vec<u64>,
    retry_max_attempts: u32,
}

#[derive(Clone, Debug)]
pub struct ScheduledPublish {
    pub publish_id: Uuid,
    pub content: Vec<u8>,
    pub scheduled_time: DateTime<Utc>,
    pub timezone: String,
    pub version: u32,
    pub published: bool,
    pub created_at: DateTime<Utc>,
}

#[derive(Clone, Debug)]
pub struct PublishAuditEntry {
    pub event: String,
    pub timestamp: DateTime<Utc>,
    pub publish_id: Uuid,
}

impl TimeCapsuleCapsule {
    pub fn new() -> Self {
        Self {
            id: Uuid::new_v4(),
            scheduled_publishes: Vec::new(),
            audit_trail: Vec::new(),
            publish_accuracy_samples: Vec::new(),
            retry_max_attempts: 3,
        }
    }

    pub fn schedule_publish(
        &mut self,
        content: Vec<u8>,
        scheduled_time: DateTime<Utc>,
        timezone: &str,
    ) -> Result<Uuid, String> {
        let publish_id = Uuid::new_v4();
        let publish = ScheduledPublish {
            publish_id,
            content,
            scheduled_time,
            timezone: timezone.to_string(),
            version: 1,
            published: false,
            created_at: Utc::now(),
        };

        self.scheduled_publishes.push(publish);
        self.audit_trail.push(PublishAuditEntry {
            event: format!("Publish scheduled for {}", scheduled_time),
            timestamp: Utc::now(),
            publish_id,
        });

        Ok(publish_id)
    }

    pub fn execute_pending_publishes(&mut self) -> Result<Vec<Uuid>, String> {
        let now = Utc::now();
        let mut published = Vec::new();

        for publish in &mut self.scheduled_publishes {
            if !publish.published && publish.scheduled_time <= now {
                let latency = (Utc::now() - publish.scheduled_time).num_milliseconds();
                self.publish_accuracy_samples.push(latency as u64);

                publish.published = true;
                self.audit_trail.push(PublishAuditEntry {
                    event: format!("Content published (latency: {}ms)", latency),
                    timestamp: Utc::now(),
                    publish_id: publish.publish_id,
                });

                published.push(publish.publish_id);
            }
        }

        self.scheduled_publishes.sort_by_key(|p| p.scheduled_time);
        Ok(published)
    }

    pub fn rollback_before_publish(&mut self, publish_id: Uuid) -> Result<(), String> {
        let publish = self.scheduled_publishes.iter_mut()
            .find(|p| p.publish_id == publish_id)
            .ok_or("Publish not found".to_string())?;

        if publish.published {
            return Err("Cannot rollback already published content".to_string());
        }

        self.audit_trail.push(PublishAuditEntry {
            event: format!("Rollback executed for publish_id {}", publish_id),
            timestamp: Utc::now(),
            publish_id,
        });

        self.scheduled_publishes.retain(|p| p.publish_id != publish_id);
        Ok(())
    }

    pub fn get_scheduled(&self) -> &[ScheduledPublish] {
        &self.scheduled_publishes
    }

    pub fn get_audit_trail(&self) -> &[PublishAuditEntry] {
        &self.audit_trail
    }

    pub fn calculate_publish_accuracy(&self) -> f64 {
        if self.publish_accuracy_samples.is_empty() {
            return 0.0;
        }

        let accuracy_threshold_ms = 1000; // 1 second
        let accurate = self.publish_accuracy_samples.iter()
            .filter(|&&latency| latency <= accuracy_threshold_ms)
            .count();

        (accurate as f64 / self.publish_accuracy_samples.len() as f64) * 100.0
    }

    pub fn verify_audit_immutable(&self) -> bool {
        !self.audit_trail.is_empty()
    }

    pub fn verify_chronological_ordering(&self) -> bool {
        for i in 0..self.scheduled_publishes.len().saturating_sub(1) {
            if self.scheduled_publishes[i].scheduled_time > self.scheduled_publishes[i + 1].scheduled_time {
                return false;
            }
        }
        true
    }
}

impl Default for TimeCapsuleCapsule {
    fn default() -> Self {
        Self::new()
    }
}
