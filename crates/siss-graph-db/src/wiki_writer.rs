use chrono::Utc;
use serde_json::json;
use std::path::PathBuf;
use tokio::io::AsyncWriteExt;
use uuid::Uuid;

use crate::trust_event_broadcaster::TrustUpdateSignal;

/// Append a trust anomaly event to the episodic JSONL log.
/// Creates file if missing; appends one JSON line per event.
pub async fn append_episodic_event(
    wiki_dir: PathBuf,
    signal: TrustUpdateSignal,
) -> std::io::Result<()> {
    let episodic_path = wiki_dir.join("episodic").join("trust-events.md");

    let severity =
        if signal.new_score < 25 || signal.decay_component < -50 || signal.implicit_component < -30
        {
            "critical"
        } else if signal.new_score < 50 {
            "high"
        } else {
            "medium"
        };

    let event = json!({
        "event_id": Uuid::new_v4().to_string(),
        "event_type": "trust_anomaly",
        "source_id": signal.source_id.to_string(),
        "target_id": signal.target_id.to_string(),
        "score": signal.new_score,
        "explicit_component": signal.explicit_component,
        "implicit_component": signal.implicit_component,
        "decay_component": signal.decay_component,
        "transitive_component": signal.transitive_component,
        "severity": severity,
        "timestamp": signal.timestamp.to_rfc3339(),
    });

    let line = serde_json::to_string(&event)?;

    tokio::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(episodic_path)
        .await?
        .write_all(format!("{}\n", line).as_bytes())
        .await?;

    Ok(())
}

/// Synthesize a pattern when anomalies recur >= 3 times per source_id.
/// Appends Markdown section to semantic file; idempotent (no duplicates).
/// Also writes to intelligence graph if pool is Some (fire-and-forget; graph errors don't propagate).
pub async fn synthesize_pattern(
    wiki_dir: PathBuf,
    source_id: Uuid,
    occurrence_count: usize,
    signal: TrustUpdateSignal,
    pool: Option<std::sync::Arc<sqlx::PgPool>>,
    first_detected: chrono::DateTime<chrono::Utc>,
) -> std::io::Result<()> {
    let semantic_path = wiki_dir.join("semantic").join("trust-anomalies.md");

    let dominant_cause = if signal.decay_component < -50 && signal.implicit_component < -30 {
        "mixed_decay_slash"
    } else if signal.decay_component < -50 {
        "decay_collapse"
    } else if signal.implicit_component < -30 {
        "slash_accumulation"
    } else if signal.transitive_component == Some(0) {
        "transitive_loss"
    } else {
        "unknown"
    };

    let recommended_action = match dominant_cause {
        "decay_collapse" => "Monitor recovery trajectory post-interaction; allow grace period",
        "slash_accumulation" => "Investigate slash events; query behavioral anomalies",
        "mixed_decay_slash" => "Revoke explicit trust edges; notify governance layer",
        "transitive_loss" => "Sweep eligibility revocation; re-establish tenure requirements",
        _ => "Monitor and investigate anomaly pattern",
    };

    let source_id_prefix = source_id.to_string()[..8].to_string();
    let pattern_section = format!(
        "## Anomaly Pattern: {}\n\n| Field | Value |\n|-------|-------|\n| Source Sovereign | {} |\n| Total Occurrences | {} |\n| Latest Score | {} |\n| Dominant Cause | {} |\n| First Detected | {} |\n| Last Detected | {} |\n| Recommended Action | {} |\n\n---\n\n",
        source_id_prefix,
        source_id,
        occurrence_count,
        signal.new_score,
        dominant_cause,
        signal.timestamp.date_naive(),
        signal.timestamp.date_naive(),
        recommended_action,
    );

    // Read existing content to check for duplicates
    let existing_content = match tokio::fs::read_to_string(&semantic_path).await {
        Ok(content) => content,
        Err(_) => String::new(), // File doesn't exist yet
    };

    if existing_content.contains(&format!("Anomaly Pattern: {}", source_id_prefix)) {
        // Pattern already exists; idempotent, don't append
        return Ok(());
    }

    tokio::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(semantic_path)
        .await?
        .write_all(pattern_section.as_bytes())
        .await?;

    // Fire-and-forget graph write: don't propagate graph errors to io::Result
    if let Some(pool) = pool {
        if let Err(e) = crate::repo::intelligence_graph_repo::write_trust_anomaly_pattern(
            &pool,
            source_id,
            signal.target_id,
            signal.new_score,
            dominant_cause,
            occurrence_count,
            first_detected,
            signal.timestamp,
        )
        .await
        {
            eprintln!("[graph-dual-write] write_trust_anomaly_pattern failed: {e}");
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use tempfile::TempDir;

    #[tokio::test]
    async fn test_append_episodic_event_creates_file_if_missing() {
        let temp_dir = TempDir::new().unwrap();
        let wiki_dir = temp_dir.path();
        tokio::fs::create_dir(wiki_dir.join("episodic"))
            .await
            .unwrap();

        let signal = TrustUpdateSignal {
            source_id: Uuid::new_v4(),
            target_id: Uuid::new_v4(),
            new_score: 12,
            explicit_component: 80,
            implicit_component: -41,
            decay_component: -50,
            transitive_component: None,
            timestamp: Utc::now(),
        };

        append_episodic_event(wiki_dir.to_path_buf(), signal)
            .await
            .unwrap();

        let contents = tokio::fs::read_to_string(wiki_dir.join("episodic").join("trust-events.md"))
            .await
            .unwrap();
        assert!(contents.contains("trust_anomaly"));
        assert!(contents.contains("critical"));

        let parsed: serde_json::Value = serde_json::from_str(&contents.trim()).unwrap();
        assert_eq!(parsed["event_type"], "trust_anomaly");
    }

    #[tokio::test]
    async fn test_append_episodic_event_appends_valid_jsonl() {
        let temp_dir = TempDir::new().unwrap();
        let wiki_dir = temp_dir.path();
        tokio::fs::create_dir(wiki_dir.join("episodic"))
            .await
            .unwrap();

        let signal1 = TrustUpdateSignal {
            source_id: Uuid::new_v4(),
            target_id: Uuid::new_v4(),
            new_score: 50,
            explicit_component: 60,
            implicit_component: -10,
            decay_component: 0,
            transitive_component: None,
            timestamp: Utc::now(),
        };

        let signal2 = TrustUpdateSignal {
            source_id: Uuid::new_v4(),
            target_id: Uuid::new_v4(),
            new_score: 30,
            explicit_component: 40,
            implicit_component: -20,
            decay_component: -10,
            transitive_component: None,
            timestamp: Utc::now(),
        };

        append_episodic_event(wiki_dir.to_path_buf(), signal1)
            .await
            .unwrap();
        append_episodic_event(wiki_dir.to_path_buf(), signal2)
            .await
            .unwrap();

        let contents = tokio::fs::read_to_string(wiki_dir.join("episodic").join("trust-events.md"))
            .await
            .unwrap();

        let lines: Vec<&str> = contents.lines().collect();
        assert_eq!(lines.len(), 2);

        for line in lines {
            let parsed: Result<serde_json::Value, _> = serde_json::from_str(line);
            assert!(parsed.is_ok());
        }
    }

    #[tokio::test]
    async fn test_append_multiple_events_no_overwrite() {
        let temp_dir = TempDir::new().unwrap();
        let wiki_dir = temp_dir.path();
        tokio::fs::create_dir(wiki_dir.join("episodic"))
            .await
            .unwrap();

        for i in 0..10 {
            let signal = TrustUpdateSignal {
                source_id: Uuid::new_v4(),
                target_id: Uuid::new_v4(),
                new_score: (i * 10) as i16,
                explicit_component: 50,
                implicit_component: -10,
                decay_component: 0,
                transitive_component: None,
                timestamp: Utc::now(),
            };
            append_episodic_event(wiki_dir.to_path_buf(), signal)
                .await
                .unwrap();
        }

        let contents = tokio::fs::read_to_string(wiki_dir.join("episodic").join("trust-events.md"))
            .await
            .unwrap();

        let lines: Vec<&str> = contents.lines().collect();
        assert_eq!(lines.len(), 10);

        for line in lines {
            let parsed: Result<serde_json::Value, _> = serde_json::from_str(line);
            assert!(parsed.is_ok());
        }
    }

    #[tokio::test]
    async fn test_synthesize_pattern_appends_markdown_section() {
        let temp_dir = TempDir::new().unwrap();
        let wiki_dir = temp_dir.path();
        tokio::fs::create_dir(wiki_dir.join("semantic"))
            .await
            .unwrap();

        let source_id = Uuid::new_v4();
        let signal = TrustUpdateSignal {
            source_id,
            target_id: Uuid::new_v4(),
            new_score: 12,
            explicit_component: 80,
            implicit_component: -41,
            decay_component: -51,
            transitive_component: None,
            timestamp: Utc::now(),
        };

        synthesize_pattern(wiki_dir.to_path_buf(), source_id, 3, signal.clone(), None, signal.timestamp)
            .await
            .unwrap();

        let contents =
            tokio::fs::read_to_string(wiki_dir.join("semantic").join("trust-anomalies.md"))
                .await
                .unwrap();

        assert!(contents.contains("## Anomaly Pattern:"));
        assert!(contents.contains(&source_id.to_string()[..8]));
        assert!(contents.contains("Total Occurrences"));
        assert!(contents.contains("Dominant Cause"));
        assert!(contents.contains("mixed_decay_slash"));
    }

    #[tokio::test]
    async fn test_synthesize_pattern_idempotent_on_same_source() {
        let temp_dir = TempDir::new().unwrap();
        let wiki_dir = temp_dir.path();
        tokio::fs::create_dir(wiki_dir.join("semantic"))
            .await
            .unwrap();

        let source_id = Uuid::new_v4();
        let signal = TrustUpdateSignal {
            source_id,
            target_id: Uuid::new_v4(),
            new_score: 20,
            explicit_component: 50,
            implicit_component: -30,
            decay_component: -40,
            transitive_component: None,
            timestamp: Utc::now(),
        };

        synthesize_pattern(wiki_dir.to_path_buf(), source_id, 3, signal.clone(), None, signal.timestamp)
            .await
            .unwrap();

        let contents_first =
            tokio::fs::read_to_string(wiki_dir.join("semantic").join("trust-anomalies.md"))
                .await
                .unwrap();

        synthesize_pattern(wiki_dir.to_path_buf(), source_id, 4, signal.clone(), None, signal.timestamp)
            .await
            .unwrap();

        let contents_second =
            tokio::fs::read_to_string(wiki_dir.join("semantic").join("trust-anomalies.md"))
                .await
                .unwrap();

        assert_eq!(contents_first, contents_second);
    }

    #[test]
    fn test_wiki_entry_contains_all_required_fields() {
        let signal = TrustUpdateSignal {
            source_id: Uuid::new_v4(),
            target_id: Uuid::new_v4(),
            new_score: 75,
            explicit_component: 80,
            implicit_component: 0,
            decay_component: -5,
            transitive_component: Some(10),
            timestamp: Utc::now(),
        };

        let severity = if signal.new_score < 25
            || signal.decay_component < -50
            || signal.implicit_component < -30
        {
            "critical"
        } else if signal.new_score < 50 {
            "high"
        } else {
            "medium"
        };

        let event = json!({
            "event_id": Uuid::new_v4().to_string(),
            "event_type": "trust_anomaly",
            "source_id": signal.source_id.to_string(),
            "target_id": signal.target_id.to_string(),
            "score": signal.new_score,
            "explicit_component": signal.explicit_component,
            "implicit_component": signal.implicit_component,
            "decay_component": signal.decay_component,
            "transitive_component": signal.transitive_component,
            "severity": severity,
            "timestamp": signal.timestamp.to_rfc3339(),
        });

        let json_string = serde_json::to_string(&event).unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&json_string).unwrap();

        assert!(parsed["event_id"].is_string());
        assert_eq!(parsed["event_type"], "trust_anomaly");
        assert!(parsed["source_id"].is_string());
        assert!(parsed["target_id"].is_string());
        assert!(parsed["score"].is_number());
        assert!(parsed["severity"].is_string());
        assert!(parsed["timestamp"].is_string());
    }

    #[tokio::test]
    async fn test_synthesize_pattern_with_pool_none_writes_markdown_only() {
        let temp_dir = TempDir::new().unwrap();
        let wiki_dir = temp_dir.path();
        tokio::fs::create_dir(wiki_dir.join("semantic"))
            .await
            .unwrap();

        let source_id = Uuid::new_v4();
        let signal = TrustUpdateSignal {
            source_id,
            target_id: Uuid::new_v4(),
            new_score: 20,
            explicit_component: 50,
            implicit_component: -30,
            decay_component: -40,
            transitive_component: None,
            timestamp: Utc::now(),
        };

        // Action: synthesize_pattern with pool = None (backward compat)
        let result = synthesize_pattern(
            wiki_dir.to_path_buf(),
            source_id,
            3,
            signal.clone(),
            None,
            signal.timestamp,
        )
        .await;

        // Assert: returns Ok
        assert!(result.is_ok(), "synthesize_pattern should succeed with pool=None");

        // Assert: markdown file was written
        let semantic_path = wiki_dir.join("semantic").join("trust-anomalies.md");
        assert!(
            semantic_path.exists(),
            "Semantic file should exist after synthesize_pattern"
        );

        let contents = tokio::fs::read_to_string(&semantic_path)
            .await
            .expect("Should read semantic file");

        assert!(
            contents.contains("## Anomaly Pattern:"),
            "Markdown should contain pattern section"
        );
        assert!(
            contents.contains(&source_id.to_string()[..8]),
            "Markdown should contain source_id prefix"
        );
    }
}
