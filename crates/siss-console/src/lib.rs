pub mod a11y;
pub mod types;
pub mod usb_tunnel;
pub mod ws_bridge;

pub use a11y::{A11y, VoiceOverReader};
pub use types::{AgentState, AgentStatus, ConsoleError, WsMessage};
pub use usb_tunnel::{Frame, UsbTunnel};
pub use ws_bridge::{AgentStream, AgentStreamId, WsBridge};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_console_exports() {
        // Verify all public types are accessible
        let _state = AgentState::Running;
    }
}
