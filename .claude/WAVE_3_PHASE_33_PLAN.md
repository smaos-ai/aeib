# Phase 33 — False Positive Decay Acceleration

## Context
Completes the feedback penalty loop. Phase 32 boosts signals on true positives. Phase 33 accelerates decay on false positives: matched=false → acceleration_mode=true (2-day half-life). matched=true already boosts; now also resets acceleration_mode=false (7-day half-life).

## Changes Required

### 1. signal_acceleration.rs — add reset_acceleration_mode() function
Add after line 116 (after accelerate_signal_decay_for_false_positive):
```rust
pub async fn reset_acceleration_mode(
    pool: &PgPool,
    feedback_node_id: Uuid,
) -> Result<usize, sqlx::Error> {
    // Fetch FeedbackNode
    let feedback_row = sqlx::query(
        "SELECT properties FROM graph_entities WHERE id = $1 AND label = 'FeedbackNode'",
    )
    .bind(feedback_node_id)
    .fetch_optional(pool)
    .await?;

    let feedback = match feedback_row {
        None => return Ok(0),
        Some(row) => row.get::<serde_json::Value, _>(0),
    };

    // Check if matched=true (only reset on true positives)
    let matched = feedback["matched"].as_bool().unwrap_or(false);
    if !matched {
        return Ok(0); // No reset on false positives
    }

    // Extract prediction_node_id
    let prediction_id_str = match feedback.get("prediction_node_id").and_then(|v| v.as_str()) {
        Some(id) => id,
        None => return Ok(0),
    };

    let prediction_id = match Uuid::parse_str(prediction_id_str) {
        Ok(id) => id,
        Err(_) => return Ok(0),
    };

    let prediction_row = sqlx::query(
        "SELECT properties FROM graph_entities WHERE id = $1 AND label = 'PredictionNode'",
    )
    .bind(prediction_id)
    .fetch_optional(pool)
    .await?;

    let prediction = match prediction_row {
        None => return Ok(0),
        Some(row) => row.get::<serde_json::Value, _>(0),
    };

    // Extract evidence
    let signal_breakdown = match prediction.get("signal_breakdown") {
        Some(sb) => sb,
        None => return Ok(0),
    };

    let evidence = match signal_breakdown.get("evidence") {
        Some(ev) if ev.is_array() => ev.as_array().unwrap(),
        _ => return Ok(0),
    };

    // Reset each signal
    let mut reset_count = 0;

    for evidence_item in evidence {
        let signal_type = match evidence_item.get("signal_type").and_then(|v| v.as_str()) {
            Some(t) => t,
            None => continue,
        };

        let signal_id = match evidence_item.get("signal_id").and_then(|v| v.as_str()) {
            Some(id_str) => match Uuid::parse_str(id_str) {
                Ok(id) => id,
                Err(_) => continue,
            },
            None => continue,
        };

        let signal_row =
            sqlx::query("SELECT properties FROM graph_entities WHERE id = $1 AND label = $2")
                .bind(signal_id)
                .bind(signal_type)
                .fetch_optional(pool)
                .await?;

        let mut signal_props = match signal_row {
            None => continue,
            Some(row) => row.get::<serde_json::Value, _>(0),
        };

        // Set acceleration_mode to false
        signal_props["acceleration_mode"] = serde_json::json!(false);

        sqlx::query(
            "INSERT INTO graph_entities (id, label, properties)
             VALUES ($1, $2, $3)
             ON CONFLICT (id) DO UPDATE SET properties = $3",
        )
        .bind(signal_id)
        .bind(signal_type)
        .bind(signal_props)
        .execute(pool)
        .await?;

        reset_count += 1;
    }

    Ok(reset_count)
}
```

### 2. signal_acceleration.rs — fix tests 7 & 8
Test 7 line 726-729: Change from `assert!(!acceleration_mode, "...before integration")` to `assert!(acceleration_mode, "Signal should have acceleration_mode=true after FP")`

Test 8 line 818-822: Change from `assert!(acceleration_mode, "...before integration")` to `assert!(!acceleration_mode, "Signal should have acceleration_mode=false after TP")`

### 3. feedback_recorder.rs — wire both calls (lines 95-99)
Replace:
```rust
if matched {
    let _ = crate::signal_reinforcement::reinforce_signals_for_feedback(pool, feedback_id).await?;
}
```
With:
```rust
if matched {
    let _ = crate::signal_reinforcement::reinforce_signals_for_feedback(pool, feedback_id).await?;
    let _ = crate::signal_acceleration::reset_acceleration_mode(pool, feedback_id).await?;
} else {
    let _ = crate::signal_acceleration::accelerate_signal_decay_for_false_positive(pool, feedback_id).await?;
}
```

### 4. lib.rs — re-export reset_acceleration_mode
Find line with `pub use signal_acceleration::accelerate_signal_decay_for_false_positive;`
Change to: `pub use signal_acceleration::{accelerate_signal_decay_for_false_positive, reset_acceleration_mode};`

## Verification Commands
```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo check -p siss-graph-db
cargo test -p siss-graph-db signal_acceleration -- --nocapture
cargo test -p siss-graph-db feedback_recorder
```

Expected: 
- cargo check passes with no errors
- signal_acceleration tests: 8 passing
- feedback_recorder tests: 8 passing
