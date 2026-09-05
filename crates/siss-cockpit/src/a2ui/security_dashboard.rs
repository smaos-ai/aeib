use siss_agent_shell::a2ui::A2UIComponent;
/// Phase 34: Security Dashboard
/// Maps AoEEvent to A2UIComponent and composes security views with Grid layout
use siss_agent_shell::ag_ui::sse_consumer::AoEEvent;

pub struct SecurityDashboard;

impl SecurityDashboard {
    /// Map AoEEvent to A2UIComponent based on action_type
    ///
    /// Mappings:
    /// - "ANOMALY_DETECTED" → Alert { variant: "destructive", title: "Security Anomaly", message: content }
    /// - "TOOL_CALL_START"  → Badge { label: content (tool name), variant: "info" }
    /// - "TEXT_MESSAGE"     → Text { content: content }
    /// - "ACTION_COMPLETED" → Badge { label: "✓ " + content, variant: "success" }
    /// - default            → Card { title: action_type, content: content }
    pub fn aoe_event_to_component(event: &AoEEvent) -> A2UIComponent {
        match event.action_type.as_str() {
            "ANOMALY_DETECTED" => A2UIComponent::Alert {
                id: event.id.clone(),
                message: event
                    .content
                    .clone()
                    .unwrap_or_else(|| "Security anomaly detected".to_string()),
                level: "error".to_string(),
            },
            "TOOL_CALL_START" => A2UIComponent::Badge {
                id: event.id.clone(),
                label: event
                    .content
                    .clone()
                    .unwrap_or_else(|| "Tool call".to_string()),
                color: Some("blue".to_string()),
            },
            "TEXT_MESSAGE" => A2UIComponent::Text {
                id: event.id.clone(),
                content: event.content.clone().unwrap_or_default(),
                size: None,
            },
            "ACTION_COMPLETED" => A2UIComponent::Badge {
                id: event.id.clone(),
                label: format!(
                    "✓ {}",
                    event
                        .content
                        .clone()
                        .unwrap_or_else(|| "Action".to_string())
                ),
                color: Some("green".to_string()),
            },
            _ => A2UIComponent::Card {
                id: event.id.clone(),
                title: Some(event.action_type.clone()),
                children: vec![A2UIComponent::Text {
                    id: format!("{}-text", event.id),
                    content: event.content.clone().unwrap_or_default(),
                    size: None,
                }],
            },
        }
    }

    /// Compose security view with Grid layout containing alerts, badges, table (if >5 events), and progress
    pub fn compose_security_view(events: Vec<AoEEvent>) -> Vec<A2UIComponent> {
        let mut alerts = Vec::new();
        let mut badges = Vec::new();
        let mut all_components = Vec::new();

        // Separate events by type for organized layout
        for event in &events {
            let component = Self::aoe_event_to_component(event);
            match &component {
                A2UIComponent::Alert { .. } => alerts.push(component.clone()),
                A2UIComponent::Badge { .. } => badges.push(component.clone()),
                _ => all_components.push(component.clone()),
            }
        }

        // Build grid with alerts first, then badges, then table if needed
        let mut result = Vec::new();

        // Add all alerts first
        result.extend(alerts);

        // Add all badges
        result.extend(badges);

        // Add table for >5 events
        if events.len() > 5 {
            let headers = vec![
                "Event Type".to_string(),
                "Status".to_string(),
                "Time".to_string(),
            ];
            let rows: Vec<Vec<String>> = events
                .iter()
                .take(10)
                .map(|e| {
                    vec![
                        e.action_type.clone(),
                        "processed".to_string(),
                        chrono::Utc::now().to_rfc3339(),
                    ]
                })
                .collect();

            result.push(A2UIComponent::Table {
                id: "security-events-table".to_string(),
                headers,
                rows,
            });
        }

        // Add progress indicator showing completion percentage
        let completed = events.len().min(100);
        result.push(A2UIComponent::Progress {
            id: "security-progress".to_string(),
            value: completed as u32,
            max: 100,
            label: Some(format!("{}/{} events processed", completed, 100)),
        });

        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_anomaly_detected_maps_to_alert() {
        let event = AoEEvent {
            action_type: "ANOMALY_DETECTED".to_string(),
            id: "evt-1".to_string(),
            content: Some("Unauthorized access".to_string()),
            metadata: None,
        };

        let component = SecurityDashboard::aoe_event_to_component(&event);

        match component {
            A2UIComponent::Alert { level, .. } => {
                assert_eq!(level, "error");
            }
            _ => panic!("Expected Alert component"),
        }
    }

    #[test]
    fn test_tool_call_maps_to_badge() {
        let event = AoEEvent {
            action_type: "TOOL_CALL_START".to_string(),
            id: "evt-2".to_string(),
            content: Some("git push".to_string()),
            metadata: None,
        };

        let component = SecurityDashboard::aoe_event_to_component(&event);

        match component {
            A2UIComponent::Badge { label, color, .. } => {
                assert_eq!(label, "git push");
                assert_eq!(color, Some("blue".to_string()));
            }
            _ => panic!("Expected Badge component"),
        }
    }

    #[test]
    fn test_text_message_preserved() {
        let event = AoEEvent {
            action_type: "TEXT_MESSAGE".to_string(),
            id: "evt-3".to_string(),
            content: Some("Operation in progress".to_string()),
            metadata: None,
        };

        let component = SecurityDashboard::aoe_event_to_component(&event);

        match component {
            A2UIComponent::Text { content, .. } => {
                assert_eq!(content, "Operation in progress");
            }
            _ => panic!("Expected Text component"),
        }
    }

    #[test]
    fn test_compose_adds_progress() {
        let events = vec![AoEEvent {
            action_type: "ACTION_COMPLETED".to_string(),
            id: "evt-1".to_string(),
            content: Some("task 1".to_string()),
            metadata: None,
        }];

        let view = SecurityDashboard::compose_security_view(events);

        // Should have Progress component
        let has_progress = view
            .iter()
            .any(|c| matches!(c, A2UIComponent::Progress { .. }));
        assert!(has_progress, "View should contain Progress component");
    }
}
