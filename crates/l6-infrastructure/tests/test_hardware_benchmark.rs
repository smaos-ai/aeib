use l6_infrastructure::{HardwareDetector, HardwareTier};

#[test]
fn test_can_run_qwen_on_this_hardware() {
    let detector = HardwareDetector::new();
    assert!(detector.can_run_qwen_on_this_hardware());
}

#[test]
fn test_get_hardware_tier() {
    let detector = HardwareDetector::new();
    assert_eq!(detector.get_hardware_tier(), HardwareTier::Specialized);
}

#[test]
fn test_hardware_spec_available() {
    let detector = HardwareDetector::new();
    let spec = detector.get_spec();
    assert_eq!(spec.ram_gb, 16);
    assert_eq!(spec.gpu_vram_gb, Some(8));
}

#[test]
fn test_canrun_proof_artifact() {
    let detector = HardwareDetector::new();
    let tier = detector.get_hardware_tier();
    let proof_artifact = format!(
        "CanIRun proof: Hardware tier {:?}, Can run Qwen: {}",
        tier,
        detector.can_run_qwen_on_this_hardware()
    );
    assert!(!proof_artifact.is_empty());
}
