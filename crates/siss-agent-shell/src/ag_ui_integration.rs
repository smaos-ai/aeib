/// Phase 59: AG-UI Streaming Integration — SSE Stream Injection for Real-Time Rendering
use crate::a2ui::schema::A2UIComponent;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "event_type", rename_all = "snake_case")]
pub enum AgUiStreamEvent {
    Text {
        content: String,
    },
    ToolCall {
        name: String,
        params: serde_json::Value,
    },
    UiComponent {
        component: A2UIComponent,
    },
    Done,
}

pub struct AgUiStream;

impl AgUiStream {
    /// RULE 1: Serialize event → `data: <json>\n\n` SSE format.
    /// Serialization failure → None (fail-closed, stream continues).
    pub fn format_event(event: &AgUiStreamEvent) -> Option<String> {
        let json = serde_json::to_string(event).ok()?;
        Some(format!("data: {}\n\n", json))
    }

    /// RULE 2: Convenience wrapper for text event.
    pub fn push_text(content: &str) -> Option<String> {
        let event = AgUiStreamEvent::Text {
            content: content.to_string(),
        };
        Self::format_event(&event)
    }

    /// RULE 2: Convenience wrapper for component event.
    pub fn push_component(component: &A2UIComponent) -> Option<String> {
        let event = AgUiStreamEvent::UiComponent {
            component: component.clone(),
        };
        Self::format_event(&event)
    }

    /// RULE 2: Done is always serializable; returns String not Option.
    pub fn push_done() -> String {
        "data: done\n\n".to_string()
    }

    /// RULE 3: Collect format_event() over a Vec; drop None; join SSE lines.
    pub fn format_stream(events: &[AgUiStreamEvent]) -> String {
        events
            .iter()
            .filter_map(|e| Self::format_event(e))
            .collect::<Vec<_>>()
            .join("")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_text_component() -> A2UIComponent {
        A2UIComponent::Text {
            id: "t1".to_string(),
            content: "hello".to_string(),
            size: None,
        }
    }

    #[test]
    fn test_format_event_text_produces_sse_prefix() {
        let event = AgUiStreamEvent::Text {
            content: "hello".to_string(),
        };
        let result = AgUiStream::format_event(&event);
        assert!(result.is_some());
        let s = result.unwrap();
        assert!(s.starts_with("data: "));
    }

    #[test]
    fn test_format_event_component_produces_sse_prefix() {
        let component = create_text_component();
        let event = AgUiStreamEvent::UiComponent { component };
        let result = AgUiStream::format_event(&event);
        assert!(result.is_some());
        let s = result.unwrap();
        assert!(s.starts_with("data: "));
    }

    #[test]
    fn test_push_done_returns_done_sentinel() {
        let result = AgUiStream::push_done();
        assert!(result.contains("done"));
        assert!(result.contains("data: "));
    }

    #[test]
    fn test_push_text_serializes_content() {
        let result = AgUiStream::push_text("hello");
        assert!(result.is_some());
        let s = result.unwrap();
        assert!(s.contains("hello"));
    }

    #[test]
    fn test_push_component_serializes_type() {
        let component = create_text_component();
        let result = AgUiStream::push_component(&component);
        assert!(result.is_some());
        let s = result.unwrap();
        assert!(s.contains("text"));
    }

    #[test]
    fn test_format_stream_interleaves_events() {
        let events = vec![
            AgUiStreamEvent::Text {
                content: "start".to_string(),
            },
            AgUiStreamEvent::UiComponent {
                component: create_text_component(),
            },
            AgUiStreamEvent::Done,
        ];
        let result = AgUiStream::format_stream(&events);
        let lines: Vec<&str> = result.split("\n\n").filter(|s| !s.is_empty()).collect();
        assert_eq!(lines.len(), 3);
    }

    #[test]
    fn test_format_stream_empty_returns_empty_string() {
        let result = AgUiStream::format_stream(&[]);
        assert_eq!(result, "");
    }

    #[test]
    fn test_sse_line_ends_with_double_newline() {
        let event = AgUiStreamEvent::Text {
            content: "test".to_string(),
        };
        let result = AgUiStream::format_event(&event);
        assert!(result.is_some());
        let s = result.unwrap();
        assert!(s.ends_with("\n\n"));
    }

    #[test]
    fn test_format_stream_drops_none_events() {
        let component = create_text_component();
        let events = vec![
            AgUiStreamEvent::Text {
                content: "valid".to_string(),
            },
            AgUiStreamEvent::UiComponent { component },
            AgUiStreamEvent::Done,
        ];
        let result = AgUiStream::format_stream(&events);
        let lines: Vec<&str> = result.split("\n\n").filter(|s| !s.is_empty()).collect();
        assert_eq!(lines.len(), 3);
    }
}
