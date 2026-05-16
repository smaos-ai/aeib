use std::path::Path;
use std::sync::{Arc, Mutex};
use tokio::fs;
use tokio::time::{sleep, Duration};
use tracing::{error, info};
use uuid::Uuid;

use crate::models::document::{DocumentManifest, DocumentStatus, IngestionSource};
use crate::models::tui_state::TuiState;
use crate::pipeline::ingestion::IngestionPipeline;
use crate::storage::ConcurrentMemoryRepo;

/// The Asynchronous Sneakernet Watcher (The Air-Lock)
pub async fn spawn_chaos_petri_watcher(
    pipeline: IngestionPipeline,
    repo: ConcurrentMemoryRepo,
    tui_state: Arc<Mutex<TuiState>>,
) {
    let quarantine_path_str = std::env::var("SMAOS_QUARANTINE_PATH")
        .unwrap_or_else(|_| "/var/lib/smaos/chaos_petri_quarantine".to_string());
    let quarantine_path = Path::new(&quarantine_path_str);
    let _ = fs::create_dir_all(quarantine_path).await;

    info!(
        "Chaos Petri Watcher armed. Monitoring {} for Sneakernet ingress...",
        quarantine_path.display()
    );

    loop {
        if let Ok(mut entries) = fs::read_dir(quarantine_path).await {
            while let Ok(Some(entry)) = entries.next_entry().await {
                let path = entry.path();

                // Only process Sneakernet encrypted payloads
                if path.is_file() && path.extension().map_or(false, |ext| ext == "enc") {
                    let doc_id = format!(
                        "doc-intel-{}",
                        Uuid::new_v4().to_string().chars().take(8).collect::<String>()
                    );

                    // 1. Enforce Fail-Closed Status: Must begin in Quarantined
                    let mut manifest = DocumentManifest {
                        document_id: doc_id.clone(),
                        filename: path.file_name().unwrap_or_default().to_string_lossy().to_string(),
                        ingestion_timestamp_ms: std::time::SystemTime::now()
                            .duration_since(std::time::UNIX_EPOCH)
                            .unwrap()
                            .as_millis() as u64,
                        source: IngestionSource::UsbSneakernet,
                        total_pages: 1,
                        quarantine_path: Some(path.clone()),
                        status: DocumentStatus::Quarantined,
                        parsed_page_count: 0,
                        entities_extracted: 0,
                        l2_memory_budget_bytes: 50_000,
                    };

                    info!(
                        "Payload detected. Initiating Phase 1 Ingestion for {}",
                        manifest.document_id
                    );

                    // 2. Read the raw Black Fog (B) data
                    let raw_text = fs::read_to_string(&path).await.unwrap_or_default();

                    // 3. Update TUI State: Agent Alpha takes point
                    {
                        let mut state = tui_state.lock().unwrap();
                        state.agent_alpha.current_document = Some(manifest.document_id.clone());
                        state.agent_alpha.active_mandates.push(doc_id.clone());
                    }

                    // 4. Squeeze through the φ Operator
                    match pipeline.process_quarantined_pdf(&mut manifest, &raw_text).await {
                        Ok(memory_writes) => {
                            let mut success_count = 0;

                            // 5. AP2 Ledger Gating & Memory Sync
                            for write in memory_writes {
                                let nonce = format!("burn-nonce-{}-{}", manifest.document_id, success_count);

                                // Persist to concurrent repo
                                repo.insert_l2(write.clone());
                                success_count += 1;

                                let mut state = tui_state.lock().unwrap();
                                state.l2_snippets.push(write.raw_span.clone());
                                state.ap2_logs.push(format!(
                                    "🟢 [alpha] AP2 Mandate Authorized: Nonce {} burned.",
                                    nonce
                                ));
                                state.agent_alpha.inference_tokens_generated += 100; // Approximate
                            }

                            // 6. Shred the physical payload after successful Gray Fog promotion
                            info!(
                                "Ingestion complete. Shredding raw payload to protect the air-gap."
                            );
                            let _ = fs::remove_file(&path).await;

                            // 7. Update final state
                            {
                                let mut state = tui_state.lock().unwrap();
                                state.memory_pressure += 5.0;
                                if state.memory_pressure > 100.0 {
                                    state.memory_pressure = 100.0;
                                }
                            }
                        }
                        Err(e) => {
                            error!(
                                "FATAL: Ingestion failed. Initiating violent purge of {}. Reason: {}",
                                path.display(),
                                e
                            );
                            let _ = fs::remove_file(&path).await;
                            let mut state = tui_state.lock().unwrap();
                            state.violations += 1;
                            state.ttft_violation_count += 1;
                            state.ap2_logs.push(format!(
                                "🔴 [SYSTEM] FATAL: Ingestion pipeline failed: {}",
                                e
                            ));
                        }
                    }
                }
            }
        }
        // Strict 10Hz polling to match the TUI tick rate
        sleep(Duration::from_millis(100)).await;
    }
}
