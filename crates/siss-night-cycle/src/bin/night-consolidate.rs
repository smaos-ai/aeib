use siss_night_cycle::NightCycleConsolidator;
use std::path::PathBuf;

fn main() -> std::io::Result<()> {
    let workspace_root = PathBuf::from("/Users/andriileukhin/Documents/SovereignNexus");

    let exec_log_path = workspace_root.join("EXEC_LOG.json");
    let metrics_db_path = workspace_root.join(".claude/night_metrics.db");
    let config_log_path = workspace_root.join("CONFIG_EVOLUTION.jsonl");
    let verification_report_path = workspace_root.join("VERIFICATION_REPORT.json");

    println!("[NightConsolidate] Starting offline consolidation...");
    println!("[NightConsolidate] EXEC_LOG: {}", exec_log_path.display());
    println!("[NightConsolidate] Metrics DB: {}", metrics_db_path.display());
    println!("[NightConsolidate] Config Log: {}", config_log_path.display());
    println!("[NightConsolidate] Report Output: {}", verification_report_path.display());

    let consolidator = NightCycleConsolidator::new(
        exec_log_path,
        metrics_db_path,
        config_log_path,
        verification_report_path.clone(),
    );

    consolidator.run_consolidation()?;

    println!("[NightConsolidate] ✓ Consolidation complete");
    println!("[NightConsolidate] Verification report written to: {}", verification_report_path.display());

    Ok(())
}
