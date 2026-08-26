//! L5: MCP servers + Agent-to-Agent communication
//! Standardized endpoint communication, API integration, message routing

pub mod mcp;
pub mod a2a;

pub use mcp::{McpServer, ServerType};
pub use a2a::{A2aMessage, A2aRouter};
