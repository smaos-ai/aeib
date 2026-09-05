use std::sync::Arc;
use std::time::Duration;
use tokio::sync::mpsc::Receiver;
use tracing::warn;

use crate::memory::operators::CartographicOperators;
use crate::memory::zonal::{GrayFog, RawObservation};

pub struct AutoDream;

impl AutoDream {
    pub fn spawn(
        receiver: Receiver<RawObservation>,
        fog: Arc<parking_lot::RwLock<GrayFog>>,
        ops: CartographicOperators,
        cycle_interval_ms: u64,
    ) -> tokio::task::JoinHandle<()> {
        tokio::spawn(Self::background_worker(
            receiver,
            fog,
            ops,
            cycle_interval_ms,
        ))
    }

    async fn background_worker(
        mut receiver: Receiver<RawObservation>,
        fog: Arc<parking_lot::RwLock<GrayFog>>,
        ops: CartographicOperators,
        cycle_interval_ms: u64,
    ) {
        let cycle_duration = Duration::from_millis(cycle_interval_ms);

        loop {
            tokio::time::sleep(cycle_duration).await;

            // Drain all pending observations
            let mut drained = Vec::new();
            while let Ok(obs) = receiver.try_recv() {
                drained.push(obs);
            }

            if drained.is_empty() {
                continue;
            }

            // Run consolidation pipeline: ϕ → α → λ
            match ops.run_cycle(drained) {
                Ok(new_fog) => {
                    // Atomically swap the new fog
                    let mut guard = fog.write();
                    *guard = new_fog;
                    drop(guard);
                }
                Err(e) => {
                    warn!("auto_dream cycle error: {e}");
                    // Old fog preserved on error (fail-closed)
                    continue;
                }
            }
        }
    }
}
