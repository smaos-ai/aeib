use crate::models::TuiState;
use siss_enclave::ledger::Ap2Ledger;

pub struct App {
    pub state: TuiState,
    pub ledger: Ap2Ledger,
    pub should_quit: bool,
}

impl App {
    pub fn new() -> Self {
        Self {
            state: TuiState::new(),
            ledger: Ap2Ledger::new(),
            should_quit: false,
        }
    }

    pub fn tick(&mut self) {
        // Update last activity timestamps
    }

    pub fn on_key(&mut self, key: char) {
        match key {
            'q' | 'Q' => self.should_quit = true,
            _ => {}
        }
    }
}
