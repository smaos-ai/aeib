use serde::{Deserialize, Serialize};

/// Deployment notification types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum NotificationType {
    DeploymentStarted,
    DeploymentSucceeded,
    DeploymentFailed,
    RollbackTriggered,
    DriftDetected,
}

/// Notification message for webhook delivery
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationMessage {
    pub notification_type: NotificationType,
    pub cluster: String,
    pub app_name: String,
    pub commit_hash: String,
    pub message: String,
    pub status: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

/// Slack webhook payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SlackPayload {
    pub text: String,
    pub attachments: Option<Vec<SlackAttachment>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SlackAttachment {
    pub color: String,
    pub title: String,
    pub fields: Vec<SlackField>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SlackField {
    pub title: String,
    pub value: String,
    pub short: bool,
}

impl NotificationMessage {
    pub fn new(
        notification_type: NotificationType,
        cluster: String,
        app_name: String,
        commit_hash: String,
        message: String,
    ) -> Self {
        let status = match notification_type {
            NotificationType::DeploymentSucceeded => "SUCCESS",
            NotificationType::DeploymentFailed => "FAILED",
            _ => "PENDING",
        }
        .to_string();

        Self {
            notification_type,
            cluster,
            app_name,
            commit_hash,
            message,
            status,
            timestamp: chrono::Utc::now(),
        }
    }

    pub fn to_slack_payload(&self) -> SlackPayload {
        let color = match self.notification_type {
            NotificationType::DeploymentSucceeded => "#36a64f".to_string(),
            NotificationType::DeploymentFailed => "#ff0000".to_string(),
            NotificationType::RollbackTriggered => "#ff9900".to_string(),
            NotificationType::DriftDetected => "#ffcc00".to_string(),
            NotificationType::DeploymentStarted => "#0099ff".to_string(),
        };

        let title = format!("Deployment {} - {}", self.status, self.app_name);

        let commit_short = if self.commit_hash.len() >= 8 {
            self.commit_hash[..8].to_string()
        } else {
            self.commit_hash.clone()
        };

        let attachment = SlackAttachment {
            color,
            title,
            fields: vec![
                SlackField {
                    title: "Cluster".to_string(),
                    value: self.cluster.clone(),
                    short: true,
                },
                SlackField {
                    title: "Commit".to_string(),
                    value: commit_short,
                    short: true,
                },
                SlackField {
                    title: "Message".to_string(),
                    value: self.message.clone(),
                    short: false,
                },
            ],
        };

        SlackPayload {
            text: format!("Deployment event: {}", self.app_name),
            attachments: Some(vec![attachment]),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_notification_message_creation() {
        let msg = NotificationMessage::new(
            NotificationType::DeploymentSucceeded,
            "aws-us-east-1".to_string(),
            "sovereign-nexus".to_string(),
            "abc123def456".to_string(),
            "Deployment completed successfully".to_string(),
        );

        assert_eq!(msg.status, "SUCCESS");
        assert_eq!(msg.cluster, "aws-us-east-1");
    }

    #[test]
    fn test_slack_payload_generation() {
        let msg = NotificationMessage::new(
            NotificationType::DeploymentSucceeded,
            "gcp-europe".to_string(),
            "app1".to_string(),
            "def456".to_string(),
            "All services healthy".to_string(),
        );

        let payload = msg.to_slack_payload();
        assert!(payload.text.contains("Deployment event"));
        assert!(payload.attachments.is_some());

        let attachments = payload.attachments.unwrap();
        assert_eq!(attachments.len(), 1);
        assert_eq!(attachments[0].color, "#36a64f");
    }
}
