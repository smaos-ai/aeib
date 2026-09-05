/// Behavioral signal captured from agent execution events.
#[derive(Debug, Clone)]
pub enum BehavioralEvent {
    Ap2NonceBurn {
        agent_did: String,
        success: bool,
    },
    GitNexusBlastRadiusBlock {
        agent_did: String,
        affected_files: usize,
        critical_modules: usize,
    },
    QuarantineEntry {
        agent_did: String,
        violation: String,
    },
}
