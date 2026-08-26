//! L5: MCP servers + Agent-to-Agent communication
//! Standardized endpoint communication, API integration, message routing

pub mod a2a;
pub mod mcp;

pub use a2a::{A2aMessage, A2aRouter};
pub use mcp::{McpServer, ServerType};
