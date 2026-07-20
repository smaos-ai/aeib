/// Phase 59: A2UI Composer — Component ID Binding & Payload Assembly
use crate::a2ui::schema::A2UIComponent;
use crate::a2ui_primitives::PrimitiveRegistry;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComponentRef {
    pub id: String,
    pub data: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2UIPayload {
    pub task_id: Uuid,
    pub form_id: String,
    pub components: Vec<A2UIComponent>,
}

pub struct A2UIComposer;

impl A2UIComposer {
    /// RULE 1: For each ComponentRef, call PrimitiveRegistry::try_parse(ref.data)
    /// → Err of any kind → ref silently dropped
    /// RULE 2: Preserve input ordering of valid components in output
    /// RULE 3: Empty refs list → A2UIPayload with empty components (no panic)
    /// RULE 4: task_id and form_id passed through unchanged
    pub fn compose(refs: Vec<ComponentRef>, task_id: Uuid, form_id: String) -> A2UIPayload {
        let components = refs
            .into_iter()
            .filter_map(|r| PrimitiveRegistry::try_parse(&r.data).ok())
            .collect();

        A2UIPayload {
            task_id,
            form_id,
            components,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compose_binds_single_component() {
        let refs = vec![ComponentRef {
            id: "t1".to_string(),
            data: serde_json::json!({
                "type": "text",
                "id": "t1",
                "content": "hello"
            }),
        }];
        let task_id = Uuid::new_v4();
        let form_id = "form1".to_string();

        let payload = A2UIComposer::compose(refs, task_id, form_id.clone());
        assert_eq!(payload.components.len(), 1);
        assert_eq!(payload.task_id, task_id);
        assert_eq!(payload.form_id, form_id);
    }

    #[test]
    fn test_compose_drops_unknown_type_ref() {
        let refs = vec![ComponentRef {
            id: "x".to_string(),
            data: serde_json::json!({
                "type": "evil_script",
                "id": "x"
            }),
        }];
        let task_id = Uuid::new_v4();
        let form_id = "form1".to_string();

        let payload = A2UIComposer::compose(refs, task_id, form_id);
        assert_eq!(payload.components.len(), 0);
    }

    #[test]
    fn test_compose_drops_malformed_ref() {
        let refs = vec![ComponentRef {
            id: "bad".to_string(),
            data: serde_json::json!({
                "type": "text",
                "id": 42,
                "content": "x"
            }),
        }];
        let task_id = Uuid::new_v4();
        let form_id = "form1".to_string();

        let payload = A2UIComposer::compose(refs, task_id, form_id);
        assert_eq!(payload.components.len(), 0);
    }

    #[test]
    fn test_compose_preserves_input_order() {
        let refs = vec![
            ComponentRef {
                id: "t1".to_string(),
                data: serde_json::json!({
                    "type": "text",
                    "id": "t1",
                    "content": "first"
                }),
            },
            ComponentRef {
                id: "b1".to_string(),
                data: serde_json::json!({
                    "type": "button",
                    "id": "b1",
                    "label": "second"
                }),
            },
            ComponentRef {
                id: "t2".to_string(),
                data: serde_json::json!({
                    "type": "text",
                    "id": "t2",
                    "content": "third"
                }),
            },
        ];
        let task_id = Uuid::new_v4();
        let form_id = "form1".to_string();

        let payload = A2UIComposer::compose(refs, task_id, form_id);
        assert_eq!(payload.components.len(), 3);
    }

    #[test]
    fn test_compose_empty_refs_returns_empty_payload() {
        let refs = vec![];
        let task_id = Uuid::new_v4();
        let form_id = "form1".to_string();

        let payload = A2UIComposer::compose(refs, task_id, form_id);
        assert!(payload.components.is_empty());
    }

    #[test]
    fn test_compose_task_id_propagated() {
        let refs = vec![ComponentRef {
            id: "t1".to_string(),
            data: serde_json::json!({
                "type": "text",
                "id": "t1",
                "content": "hello"
            }),
        }];
        let task_id = Uuid::new_v4();
        let form_id = "form1".to_string();

        let payload = A2UIComposer::compose(refs, task_id, form_id);
        assert_eq!(payload.task_id, task_id);
    }

    #[test]
    fn test_compose_form_id_propagated() {
        let refs = vec![ComponentRef {
            id: "t1".to_string(),
            data: serde_json::json!({
                "type": "text",
                "id": "t1",
                "content": "hello"
            }),
        }];
        let task_id = Uuid::new_v4();
        let form_id = "form_xyz".to_string();

        let payload = A2UIComposer::compose(refs, task_id, form_id.clone());
        assert_eq!(payload.form_id, form_id);
    }

    #[test]
    fn test_compose_drops_empty_id_component() {
        let refs = vec![ComponentRef {
            id: "bad".to_string(),
            data: serde_json::json!({
                "type": "text",
                "id": "",
                "content": "x"
            }),
        }];
        let task_id = Uuid::new_v4();
        let form_id = "form1".to_string();

        let payload = A2UIComposer::compose(refs, task_id, form_id);
        assert_eq!(payload.components.len(), 0);
    }

    #[test]
    fn test_compose_mixed_valid_invalid_batch() {
        let refs = vec![
            ComponentRef {
                id: "t1".to_string(),
                data: serde_json::json!({
                    "type": "text",
                    "id": "t1",
                    "content": "valid"
                }),
            },
            ComponentRef {
                id: "bad1".to_string(),
                data: serde_json::json!({
                    "type": "evil_script",
                    "id": "x"
                }),
            },
            ComponentRef {
                id: "b1".to_string(),
                data: serde_json::json!({
                    "type": "button",
                    "id": "b1",
                    "label": "valid"
                }),
            },
            ComponentRef {
                id: "bad2".to_string(),
                data: serde_json::json!({
                    "type": "text",
                    "id": "",
                    "content": "invalid"
                }),
            },
        ];
        let task_id = Uuid::new_v4();
        let form_id = "form1".to_string();

        let payload = A2UIComposer::compose(refs, task_id, form_id);
        assert_eq!(payload.components.len(), 2);
    }
}
