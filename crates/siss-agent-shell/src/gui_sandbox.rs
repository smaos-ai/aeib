/// Phase 54: Headless GUI Sandbox — δ+ Jail with Exclusive Container Token
/// Non-Clone token enforces exclusive agent-to-port binding via Rust ownership.

use std::collections::HashMap;
use std::sync::Mutex;
use std::sync::Arc;
use uuid::Uuid;

pub trait ContainerDriver: Send + Sync {
    fn spawn_container(&self, port: u16, display: &str) -> Result<String, GuiSandboxError>;
    fn stop_container(&self, container_id: &str) -> Result<(), GuiSandboxError>;
}

#[derive(Debug)]  // NO Clone — intentional
pub struct GuiContainerToken {
    pub container_id: String,
    pub agent_id: Uuid,
    pub vnc_port: u16,
    pub display: String,
}

#[derive(Debug, PartialEq, Eq)]
pub enum GuiSandboxError {
    PortAlreadyAllocated { port: u16, held_by: Uuid },
    SpawnFailed(String),
    StopFailed(String),
}

pub struct GuiSandboxAllocator {
    allocated: Arc<Mutex<HashMap<u16, Uuid>>>,
}

impl GuiSandboxAllocator {
    pub fn new() -> Self {
        GuiSandboxAllocator {
            allocated: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// RULE 1: port already in map → Err(PortAlreadyAllocated)
    /// RULE 2: driver.spawn_container(port, display) fails → Err(SpawnFailed)
    /// RULE 3: Ok(GuiContainerToken) — caller holds exclusive proof
    pub fn allocate(
        &self,
        agent_id: Uuid,
        port: u16,
        display: &str,
        driver: &dyn ContainerDriver,
    ) -> Result<GuiContainerToken, GuiSandboxError> {
        let mut map = self.allocated.lock().unwrap();

        if map.contains_key(&port) {
            let held_by = map[&port];
            return Err(GuiSandboxError::PortAlreadyAllocated { port, held_by });
        }

        let container_id = driver.spawn_container(port, display)?;
        map.insert(port, agent_id);

        Ok(GuiContainerToken {
            container_id,
            agent_id,
            vnc_port: port,
            display: display.to_string(),
        })
    }

    /// Consumes token (destructs exclusive proof), stops container, removes from map
    pub fn release(
        &self,
        token: GuiContainerToken,
        driver: &dyn ContainerDriver,
    ) -> Result<(), GuiSandboxError> {
        driver.stop_container(&token.container_id)?;
        let mut map = self.allocated.lock().unwrap();
        map.remove(&token.vnc_port);
        Ok(())
    }

    pub fn is_allocated(&self, port: u16) -> bool {
        self.allocated.lock().unwrap().contains_key(&port)
    }
}

pub struct MockContainerDriver;

impl ContainerDriver for MockContainerDriver {
    fn spawn_container(&self, port: u16, display: &str) -> Result<String, GuiSandboxError> {
        Ok(format!("mock-container-{}:{}", port, display))
    }

    fn stop_container(&self, _container_id: &str) -> Result<(), GuiSandboxError> {
        Ok(())
    }
}
