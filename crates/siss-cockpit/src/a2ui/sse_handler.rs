use super::renderer::Renderer;
use chrono::Utc;
use serde::{Deserialize, Serialize};
use siss_agent_shell::a2ui::A2UIComponent;
use std::sync::{Arc, Mutex};

/// Trait to extract id from any A2UIComponent
pub trait ComponentId {
    fn id(&self) -> &str;
}

impl ComponentId for A2UIComponent {
    fn id(&self) -> &str {
        match self {
            A2UIComponent::Text { id, .. } => id,
            A2UIComponent::Badge { id, .. } => id,
            A2UIComponent::Alert { id, .. } => id,
            A2UIComponent::Progress { id, .. } => id,
            A2UIComponent::Divider { id } => id,
            A2UIComponent::Link { id, .. } => id,
            A2UIComponent::Tooltip { id, .. } => id,
            A2UIComponent::Breadcrumb { id, .. } => id,
            A2UIComponent::Input { id, .. } => id,
            A2UIComponent::Textarea { id, .. } => id,
            A2UIComponent::Select { id, .. } => id,
            A2UIComponent::Checkbox { id, .. } => id,
            A2UIComponent::Radio { id, .. } => id,
            A2UIComponent::Button { id, .. } => id,
            A2UIComponent::Card { id, .. } => id,
            A2UIComponent::Grid { id, .. } => id,
            A2UIComponent::Modal { id, .. } => id,
            A2UIComponent::Table { id, .. } => id,
        }
    }
}

/// SSE message for transmitting rendered A2UI components
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SseComponentMessage {
    pub component_id: String,
    pub form_id: String,
    pub rendered_html: String,
    pub timestamp: String,
}

impl SseComponentMessage {
    /// Create SSE message from A2UIComponent
    pub fn from_component(component: &A2UIComponent, form_id: &str) -> Self {
        use ComponentId;
        let component_id = component.id().to_string();
        let rendered_html = Renderer::render(component);
        let timestamp = Utc::now().to_rfc3339();

        Self {
            component_id,
            form_id: form_id.to_string(),
            rendered_html,
            timestamp,
        }
    }
}

/// A2UI SSE Handler: manages component streaming state and rendering
pub struct A2UISseHandler {
    streaming_state: Arc<Mutex<StreamingState>>,
}

#[derive(Debug, Clone)]
struct StreamingState {
    active: bool,
    agent_id: Option<String>,
}

impl A2UISseHandler {
    /// Create new SSE handler
    pub fn new() -> Self {
        Self {
            streaming_state: Arc::new(Mutex::new(StreamingState {
                active: false,
                agent_id: None,
            })),
        }
    }

    /// Start streaming for agent
    pub fn start_streaming(&self, agent_id: &str) {
        let mut state = self.streaming_state.lock().expect("lock poisoned");
        state.active = true;
        state.agent_id = Some(agent_id.to_string());
    }

    /// Stop streaming
    pub fn stop_streaming(&self) {
        let mut state = self.streaming_state.lock().expect("lock poisoned");
        state.active = false;
        state.agent_id = None;
    }

    /// Check if currently streaming
    pub fn is_streaming(&self) -> bool {
        let state = self.streaming_state.lock().expect("lock poisoned");
        state.active
    }

    /// Render component to SSE message
    pub fn render_component(
        &self,
        component: &A2UIComponent,
        form_id: &str,
    ) -> SseComponentMessage {
        SseComponentMessage::from_component(component, form_id)
    }
}

impl Default for A2UISseHandler {
    fn default() -> Self {
        Self::new()
    }
}
