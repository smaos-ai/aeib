use serde_json::{json, Value};

use crate::types::{AgentCard, SerializeOptions};

/// Serialize an `AgentCard` to a Google A2A-compatible JSON value.
///
/// Standard fields are always emitted. When `opts.extended` is true, an
/// `x-siss` block is added with SISS-native fields.
pub fn to_a2a_json(card: &AgentCard, opts: &SerializeOptions) -> Value {
    let skills: Vec<Value> = card.skills.iter().map(|s| {
        json!({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "tags": s.tags,
        })
    }).collect();

    let mut obj = json!({
        "name": card.node.name,
        "description": card.node.description,
        "version": card.node.version,
        "url": card.node.url,
        "skills": skills,
        "capabilities": {
            "streaming": card.capabilities.streaming,
            "pushNotifications": card.capabilities.push_notifications,
        },
        "authentication": {
            "schemes": card.authentication.schemes,
        },
    });

    if opts.extended {
        let hw_str = match card.node.hardware_affinity {
            siss_graph_core::node::execution::HardwareTarget::LocalMlx => "local_mlx",
            siss_graph_core::node::execution::HardwareTarget::RemoteFrontier => "remote_frontier",
            siss_graph_core::node::execution::HardwareTarget::Hybrid => "hybrid",
        };
        obj["x-siss"] = json!({
            "persona_id": card.node.persona_id.0.to_string(),
            "tenant_id": card.node.tenant_id.0.to_string(),
            "hardware_affinity": hw_str,
            "budget_cap": card.node.budget_cap,
        });
    }

    obj
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use siss_graph_core::node::NodeId;
    use siss_graph_core::node::execution::HardwareTarget;
    use uuid::Uuid;

    use crate::types::{AgentCardNode, AgentCard, Authentication, Capability, Skill};

    fn make_card() -> AgentCard {
        let node = AgentCardNode {
            id: NodeId(Uuid::nil()),
            persona_id: NodeId(Uuid::nil()),
            tenant_id: NodeId(Uuid::nil()),
            name: "Aria".into(),
            description: "Test agent".into(),
            version: "0.2.0".into(),
            url: "https://example.com/agent".into(),
            hardware_affinity: HardwareTarget::RemoteFrontier,
            budget_cap: 200_000,
            allowed_tools: vec![],
            created_at: Utc::now(),
        };
        AgentCard {
            node,
            skills: vec![
                Skill {
                    id: "mcp_filesystem".into(),
                    name: "MCP Filesystem".into(),
                    description: "Read and write files".into(),
                    tags: vec!["filesystem".into()],
                },
            ],
            capabilities: Capability { streaming: true, push_notifications: false },
            authentication: Authentication { schemes: vec!["Bearer".into()] },
        }
    }

    #[test]
    fn test_standard_fields_present() {
        let card = make_card();
        let json = to_a2a_json(&card, &SerializeOptions { extended: false });

        assert_eq!(json["name"], "Aria");
        assert_eq!(json["description"], "Test agent");
        assert_eq!(json["version"], "0.2.0");
        assert_eq!(json["url"], "https://example.com/agent");
    }

    #[test]
    fn test_capabilities_camel_case() {
        let card = make_card();
        let json = to_a2a_json(&card, &SerializeOptions { extended: false });

        assert_eq!(json["capabilities"]["streaming"], true);
        assert_eq!(json["capabilities"]["pushNotifications"], false);
        // pushNotifications must be camelCase, not snake_case
        assert!(json["capabilities"].get("push_notifications").is_none());
    }

    #[test]
    fn test_authentication_schemes() {
        let card = make_card();
        let json = to_a2a_json(&card, &SerializeOptions { extended: false });

        let schemes = &json["authentication"]["schemes"];
        assert_eq!(schemes[0], "Bearer");
    }

    #[test]
    fn test_skills_serialized() {
        let card = make_card();
        let json = to_a2a_json(&card, &SerializeOptions { extended: false });

        let skills = &json["skills"];
        assert_eq!(skills[0]["id"], "mcp_filesystem");
        assert_eq!(skills[0]["name"], "MCP Filesystem");
        assert_eq!(skills[0]["tags"][0], "filesystem");
    }

    #[test]
    fn test_x_siss_block_absent_when_not_extended() {
        let card = make_card();
        let json = to_a2a_json(&card, &SerializeOptions { extended: false });
        assert!(json.get("x-siss").is_none());
    }

    #[test]
    fn test_x_siss_block_present_when_extended() {
        let card = make_card();
        let json = to_a2a_json(&card, &SerializeOptions { extended: true });

        let x_siss = &json["x-siss"];
        assert_eq!(x_siss["persona_id"], "00000000-0000-0000-0000-000000000000");
        assert_eq!(x_siss["tenant_id"], "00000000-0000-0000-0000-000000000000");
        assert_eq!(x_siss["hardware_affinity"], "remote_frontier");
        assert_eq!(x_siss["budget_cap"], 200_000i64);
    }

    #[test]
    fn test_empty_skills_list() {
        let mut card = make_card();
        card.skills.clear();
        let json = to_a2a_json(&card, &SerializeOptions { extended: false });
        assert_eq!(json["skills"], serde_json::json!([]));
    }
}
