use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::broadcast;
use uuid::Uuid;

use crate::trust_event_broadcaster::TrustUpdateSignal;
use crate::wiki_writer;

/// Determine if a trust update signal represents a severe penalty.
pub fn is_severe_penalty(signal: &TrustUpdateSignal) -> bool {
    signal.new_score < 25 || signal.decay_component < -50 || signal.implicit_component < -30
}

/// State tracking for each source_id: occurrence count and first detection timestamp
struct AnomalyState {
    count: usize,
    first_detected: chrono::DateTime<chrono::Utc>,
}

/// Start the AutoResearch watcher loop. Subscribes to trust signals, detects severe penalties,
/// appends episodic events, and synthesizes patterns when threshold (≥3 occurrences) is reached.
pub fn start_autoresearch_watcher(
    mut rx: broadcast::Receiver<TrustUpdateSignal>,
    wiki_dir: PathBuf,
    pool: Option<Arc<sqlx::PgPool>>,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        let wiki_dir = Arc::new(wiki_dir);
        let mut occurrence_state: HashMap<Uuid, AnomalyState> = HashMap::new();

        loop {
            match rx.recv().await {
                Ok(signal) => {
                    if is_severe_penalty(&signal) {
                        if let Err(e) =
                            wiki_writer::append_episodic_event((*wiki_dir).clone(), signal.clone())
                                .await
                        {
                            eprintln!("Failed to write episodic event: {}", e);
                        }

                        let state = occurrence_state.entry(signal.source_id).or_insert(AnomalyState {
                            count: 0,
                            first_detected: signal.timestamp,
                        });
                        state.count += 1;

                        if state.count >= 3 {
                            if let Err(e) = wiki_writer::synthesize_pattern(
                                (*wiki_dir).clone(),
                                signal.source_id,
                                state.count,
                                signal.clone(),
                                pool.clone(),
                                state.first_detected,
                            )
                            .await
                            {
                                eprintln!("Failed to synthesize pattern: {}", e);
                            }
                        }
                    }
                }
                Err(broadcast::error::RecvError::Lagged(_)) => {
                    // Missed events due to subscriber lag; continue
                    continue;
                }
                Err(broadcast::error::RecvError::Closed) => {
                    // Broadcaster closed; exit watcher
                    break;
                }
            }
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use uuid::Uuid;

    #[test]
    fn test_is_severe_score_below_25() {
        let signal = TrustUpdateSignal {
            source_id: Uuid::nil(),
            target_id: Uuid::nil(),
            new_score: 12,
            explicit_component: 0,
            implicit_component: 0,
            decay_component: 0,
            transitive_component: None,
            timestamp: Utc::now(),
        };
        assert!(is_severe_penalty(&signal));
    }

    #[test]
    fn test_is_severe_decay_below_50() {
        let signal = TrustUpdateSignal {
            source_id: Uuid::nil(),
            target_id: Uuid::nil(),
            new_score: 50,
            explicit_component: 0,
            implicit_component: 0,
            decay_component: -51,
            transitive_component: None,
            timestamp: Utc::now(),
        };
        assert!(is_severe_penalty(&signal));
    }

    #[test]
    fn test_is_severe_slash_implicit_below_30() {
        let signal = TrustUpdateSignal {
            source_id: Uuid::nil(),
            target_id: Uuid::nil(),
            new_score: 50,
            explicit_component: 0,
            implicit_component: -31,
            decay_component: 0,
            transitive_component: None,
            timestamp: Utc::now(),
        };
        assert!(is_severe_penalty(&signal));
    }

    #[test]
    fn test_not_severe_above_all_thresholds() {
        let signal = TrustUpdateSignal {
            source_id: Uuid::nil(),
            target_id: Uuid::nil(),
            new_score: 30,
            explicit_component: 0,
            implicit_component: -10,
            decay_component: -10,
            transitive_component: None,
            timestamp: Utc::now(),
        };
        assert!(!is_severe_penalty(&signal));
    }
}
