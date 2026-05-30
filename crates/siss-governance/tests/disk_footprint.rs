use siss_governance::{DecisionRecord, DecisionStore};
use siss_governance::decision_store::DecisionDb;
use tempfile::NamedTempFile;

#[test]
fn test_disk_footprint_1000_records() {
    let temp_file = NamedTempFile::new().expect("temp file");
    let db = DecisionDb::new(Some(temp_file.path().to_path_buf())).expect("db creation");

    // Insert 1000 records
    for i in 0..1000 {
        let rec = DecisionRecord {
            category: format!("cat_{}", i % 10),
            context: format!(
                "This is context number {} with some repeated text to simulate realistic sizes",
                i
            ),
            decision: format!(
                "This is decision number {} with more detailed reasoning text to fill space",
                i
            ),
        };
        db.record(rec).expect(&format!("record {}", i));
    }

    // Verify chain
    let valid = db.verify_chain().expect("verify");
    assert!(valid, "chain should be valid");

    // Check file size
    let metadata = std::fs::metadata(temp_file.path()).expect("metadata");
    let size_mb = metadata.len() as f64 / (1024.0 * 1024.0);
    println!("Database size after 1000 records: {:.2} MB", size_mb);
    assert!(size_mb < 5.0, "Database should be < 5MB, got {:.2}MB", size_mb);
}
