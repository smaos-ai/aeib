// HarnessCapsule v1: Framework Integration Layer
// Routes policy checks through adapters (LangChain, Ollama, AutoGPT)

use crate::types::HarnessConfig;
use std::sync::Arc;
use std::collections::HashMap;
use parking_lot::Mutex;

pub struct HarnessCapsule {
    config: HarnessConfig,
    request_counter: Arc<Mutex<usize>>,
    #[allow(dead_code)]
    active_requests: Arc<Mutex<HashMap<String, bool>>>,
}

impl HarnessCapsule {
    pub fn new(config: HarnessConfig) -> Self {
        HarnessCapsule {
            config,
            request_counter: Arc::new(Mutex::new(0)),
            active_requests: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub fn config(&self) -> &HarnessConfig {
        &self.config
    }

    pub fn increment_request_count(&self) {
        let mut counter = self.request_counter.lock();
        *counter += 1;
    }

    pub fn get_request_count(&self) -> usize {
        *self.request_counter.lock()
    }
}
