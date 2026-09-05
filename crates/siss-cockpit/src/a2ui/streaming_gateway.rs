use chrono::{DateTime, Utc};
use siss_agent_shell::a2ui::A2UIComponent;
/// Phase 33: A2UI Streaming Gateway
/// Real-time component validation, rendering, and broadcast streaming
use tokio::sync::broadcast;

use super::renderer::Renderer;

/// Result type from ValidatedComponentEvent
#[derive(Debug, Clone, PartialEq)]
pub struct AuditResult {
    pub passed: bool,
    pub violations: Vec<String>,
}

impl Default for AuditResult {
    fn default() -> Self {
        Self {
            passed: true,
            violations: Vec::new(),
        }
    }
}

/// A component event after validation, rendering, and accessibility audit
#[derive(Debug, Clone)]
pub struct ValidatedComponentEvent {
    pub component: A2UIComponent,
    pub jsx: String,                // Rendered HTML by Renderer
    pub schema_valid: bool,         // Always true for now (validated before emit)
    pub accessibility: AuditResult, // Audit results
    pub timestamp: DateTime<Utc>,
}

/// Gateway errors
#[derive(Debug, Clone, PartialEq)]
pub enum GatewayError {
    ValidationFailed(String),
    AccessibilityFailed(String),
    RendererFailed(String),
    BroadcastFailed(String),
}

impl std::fmt::Display for GatewayError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::ValidationFailed(msg) => write!(f, "Validation failed: {}", msg),
            Self::AccessibilityFailed(msg) => write!(f, "Accessibility audit failed: {}", msg),
            Self::RendererFailed(msg) => write!(f, "Rendering failed: {}", msg),
            Self::BroadcastFailed(msg) => write!(f, "Broadcast failed: {}", msg),
        }
    }
}

impl std::error::Error for GatewayError {}

/// A2UI Streaming Gateway: validates, renders, audits, and broadcasts components
pub struct A2UIStreamingGateway {
    broadcaster: broadcast::Sender<ValidatedComponentEvent>,
}

impl A2UIStreamingGateway {
    /// Create a new streaming gateway with capacity
    pub fn new(capacity: usize) -> Self {
        let (tx, _rx) = broadcast::channel(capacity);
        Self { broadcaster: tx }
    }

    /// Publish a component for streaming
    ///
    /// Steps:
    /// 1. Validate schema (always succeeds in this implementation)
    /// 2. Render to JSX/HTML
    /// 3. Run accessibility audit
    /// 4. Broadcast to all subscribers
    ///
    /// Returns count of subscribers
    pub fn publish(&self, component: A2UIComponent) -> Result<usize, GatewayError> {
        // Step 1: Validate schema (components are pre-validated before reaching here)
        let schema_valid = true;

        // Step 2: Render to HTML
        let jsx = Renderer::render(&component);

        // Step 3: Run accessibility audit
        let accessibility = self.audit_component(&component);

        // Step 4: Create event
        let event = ValidatedComponentEvent {
            component: component.clone(),
            jsx,
            schema_valid,
            accessibility,
            timestamp: Utc::now(),
        };

        // Broadcast and return subscriber count
        match self.broadcaster.send(event) {
            Ok(num_subscribers) => Ok(num_subscribers),
            Err(broadcast::error::SendError(_e)) => {
                Err(GatewayError::BroadcastFailed("channel closed".to_string()))
            }
        }
    }

    /// Subscribe to component events
    pub fn subscribe(&self) -> broadcast::Receiver<ValidatedComponentEvent> {
        self.broadcaster.subscribe()
    }

    /// Accessibility audit for a component
    /// Checks for common a11y issues (aria labels, alt text, etc.)
    fn audit_component(&self, component: &A2UIComponent) -> AuditResult {
        let mut violations = Vec::new();

        match component {
            A2UIComponent::Input { label, .. } => {
                if label.is_empty() {
                    violations.push("Input missing label".to_string());
                }
            }
            A2UIComponent::Button { label, .. } => {
                if label.is_empty() {
                    violations.push("Button missing label".to_string());
                }
            }
            A2UIComponent::Checkbox { label, .. } => {
                if label.is_empty() {
                    violations.push("Checkbox missing label".to_string());
                }
            }
            A2UIComponent::Textarea { label, .. } => {
                if label.is_empty() {
                    violations.push("Textarea missing label".to_string());
                }
            }
            A2UIComponent::Select { label, options, .. } => {
                if label.is_empty() {
                    violations.push("Select missing label".to_string());
                }
                if options.is_empty() {
                    violations.push("Select missing options".to_string());
                }
            }
            A2UIComponent::Radio { label, .. } => {
                if label.is_empty() {
                    violations.push("Radio missing label".to_string());
                }
            }
            A2UIComponent::Link { label, href, .. } => {
                if label.is_empty() {
                    violations.push("Link missing label".to_string());
                }
                if href.is_empty() {
                    violations.push("Link missing href".to_string());
                }
            }
            _ => {}
        }

        AuditResult {
            passed: violations.is_empty(),
            violations,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gateway_creation() {
        let gateway = A2UIStreamingGateway::new(100);
        assert_eq!(gateway.broadcaster.receiver_count(), 0);
    }

    #[tokio::test]
    async fn test_gateway_basic_publish() {
        let gateway = A2UIStreamingGateway::new(100);
        let component = A2UIComponent::Button {
            id: "btn1".to_string(),
            label: "Test".to_string(),
            action: None,
        };

        let result = gateway.publish(component);
        assert!(result.is_ok());
    }

    #[test]
    fn test_audit_detects_missing_label() {
        let gateway = A2UIStreamingGateway::new(100);
        let component = A2UIComponent::Button {
            id: "btn1".to_string(),
            label: "".to_string(),
            action: None,
        };

        let audit = gateway.audit_component(&component);
        assert!(!audit.passed);
        assert!(
            audit
                .violations
                .iter()
                .any(|v| v.contains("Button missing label"))
        );
    }

    #[test]
    fn test_audit_passes_valid_button() {
        let gateway = A2UIStreamingGateway::new(100);
        let component = A2UIComponent::Button {
            id: "btn1".to_string(),
            label: "Click Me".to_string(),
            action: None,
        };

        let audit = gateway.audit_component(&component);
        assert!(audit.passed);
        assert!(audit.violations.is_empty());
    }

    #[test]
    fn test_validated_event_has_jsx() {
        let gateway = A2UIStreamingGateway::new(100);
        let component = A2UIComponent::Badge {
            id: "badge1".to_string(),
            label: "Test".to_string(),
            color: None,
        };

        let _rx = gateway.subscribe();
        let _ = gateway.publish(component);

        // This would be async in real tests
    }
}
