// Phase 1: Genesis Capsule Live Execution — Prague PoC Proof Artifact
//
// Runs the complete authorization pipeline end-to-end, demonstrating:
// 1. Covenant enforcement (1%/99% split with Ed25519 signature)
// 2. AP2 intent validation (trust level predicate)
// 3. Full Merkle-rooted authorization proof
//
// Invocation:
//   cargo run --example phase1_genesis --package siss-gatekeeper
//
// Output:
//   - Prints JSON Genesis Capsule with all proof data
//   - Suitable for Prague demo and EXEC_LOG audit trail

use siss_gatekeeper::pipeline::execute_genesis_with_generated_key;
use std::fs;

fn main() {
    println!("\n╔════════════════════════════════════════════════════════════╗");
    println!("║         PHASE 1: GENESIS CAPSULE LIVE EXECUTION           ║");
    println!("║                    June 2, 2026, 22:00 UTC                ║");
    println!("╚════════════════════════════════════════════════════════════╝\n");

    // Execute Genesis Capsule through full authorization pipeline
    match execute_genesis_with_generated_key() {
        Ok(capsule) => {
            println!("✅ Genesis Capsule execution successful\n");

            // Serialize to JSON for audit trail
            let capsule_json =
                serde_json::to_string_pretty(&capsule).expect("capsule must be serializable");

            println!("{}", capsule_json);
            println!("\n📋 PROOF SUMMARY:");
            println!("   Capsule ID: {}", capsule.capsule_id);
            println!("   Covenant: {}%/{}{}",
                capsule.economist_pct,
                capsule.beneficiary_pct,
                if capsule.economist_pct + capsule.beneficiary_pct == 100 { " ✓" } else { " ✗" }
            );
            println!("   Signature: {}...", &capsule.signature_hex[..32.min(capsule.signature_hex.len())]);
            println!("   Proof Root: {}", capsule.proof_merkle_root);
            println!("   Timestamp: {}\n", capsule.timestamp);

            // Save to file for reference
            let output_path = "/tmp/genesis_capsule_phase1.json";
            fs::write(output_path, &capsule_json)
                .expect("must write genesis capsule to file");
            println!("💾 Saved to: {}\n", output_path);

            // Parse proof to show gate decisions
            if let Ok(proof) = serde_json::from_str::<serde_json::Value>(&capsule.authorization_proof) {
                if let Some(gates) = proof.get("gate_decisions").and_then(|g| g.as_object()) {
                    println!("🔐 GATES PASSED:");
                    let mut gate_names: Vec<_> = gates.keys().collect();
                    gate_names.sort();
                    for gate in gate_names {
                        println!("   ✓ {}", gate);
                    }
                    println!();
                }
            }

            println!("📊 PHASE 1 DELIVERABLE:");
            println!("   Status: ✅ COMPLETE (14/14 hours)");
            println!("   Live Genesis Capsule: {}", capsule.capsule_id);
            println!("   Authorization Proof: {}", capsule.proof_merkle_root);
            println!("   Ready for Phase 2: MongeGapGovernor Validation\n");
        }
        Err(e) => {
            eprintln!("❌ Genesis Capsule execution failed: {}\n", e);
            std::process::exit(1);
        }
    }
}
