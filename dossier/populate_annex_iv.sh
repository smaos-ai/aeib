#!/bin/bash
# ANNEX IV DOSSIER — Automated Population Script
# Usage: ./populate_annex_iv.sh <pilot_data_dir> <output_file>
# Merges real pilot execution data into annex_iv_structure.json

set -e

PILOT_DATA_DIR="${1:-.}"
OUTPUT_FILE="${2:-annex_iv_structure.json}"
BASE_DOSSIER="annex_iv_structure.json"

if [ ! -f "$BASE_DOSSIER" ]; then
    echo "ERROR: Base dossier ($BASE_DOSSIER) not found"
    exit 1
fi

echo "Populating ANNEX IV dossier from pilot data..."

# Helper: update nested JSON field
update_json() {
    local file=$1
    local path=$2
    local value=$3
    # Using jq for safe JSON updates
    jq --arg val "$value" ".${path} = (\$val | fromjson? // \$val)" "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
}

# Section 5: Testing & Validation - RAGAS Results
if [ -f "$PILOT_DATA_DIR/ragas_baseline.json" ]; then
    echo "Updating Section 5: RAGAS baseline results..."
    RAGAS_ACCURACY=$(jq -r '.accuracy' "$PILOT_DATA_DIR/ragas_baseline.json")
    update_json "$OUTPUT_FILE" "section_5_testing_validation.test_suite.ragas_evaluation.current_baseline" "$RAGAS_ACCURACY"
fi

# Section 5: Testing & Validation - Test Execution Results
if [ -f "$PILOT_DATA_DIR/test_results.json" ]; then
    echo "Updating Section 5: Test execution results..."
    TOTAL_TESTS=$(jq -r '.total_tests' "$PILOT_DATA_DIR/test_results.json")
    PASSED=$(jq -r '.passed' "$PILOT_DATA_DIR/test_results.json")
    DEFECT_RATE=$(jq -r '.defect_rate' "$PILOT_DATA_DIR/test_results.json")

    update_json "$OUTPUT_FILE" "section_5_testing_validation.test_suite.total_tests" "$TOTAL_TESTS"
    update_json "$OUTPUT_FILE" "section_5_testing_validation.test_suite.defect_rate.target" "$DEFECT_RATE"
fi

# Section 5: Pilot Test Results - Hotel Credit Scoring
if [ -f "$PILOT_DATA_DIR/hotel_credit_test_results.json" ]; then
    echo "Updating Section 5: Hotel credit scoring tests..."
    HOTEL_TESTS=$(jq -r '.test_count' "$PILOT_DATA_DIR/hotel_credit_test_results.json")
    HOTEL_ACCURACY=$(jq -r '.decision_accuracy' "$PILOT_DATA_DIR/hotel_credit_test_results.json")

    update_json "$OUTPUT_FILE" "section_5_testing_validation.validation_methodology.pilot_execution_tests.hotel_credit.test_cases" "$HOTEL_TESTS"
    update_json "$OUTPUT_FILE" "section_5_testing_validation.validation_methodology.pilot_execution_tests.hotel_credit.decision_accuracy" "$HOTEL_ACCURACY"
fi

# Section 5: Pilot Test Results - Glass Safety
if [ -f "$PILOT_DATA_DIR/glass_safety_test_results.json" ]; then
    echo "Updating Section 5: Glass safety tests..."
    GLASS_TESTS=$(jq -r '.test_count' "$PILOT_DATA_DIR/glass_safety_test_results.json")
    FPR=$(jq -r '.false_positive_rate' "$PILOT_DATA_DIR/glass_safety_test_results.json")
    FNR=$(jq -r '.false_negative_rate' "$PILOT_DATA_DIR/glass_safety_test_results.json")

    update_json "$OUTPUT_FILE" "section_5_testing_validation.validation_methodology.pilot_execution_tests.glass_safety.test_cases" "$GLASS_TESTS"
    update_json "$OUTPUT_FILE" "section_5_testing_validation.validation_methodology.pilot_execution_tests.glass_safety.false_positive_rate" "$FPR"
    update_json "$OUTPUT_FILE" "section_5_testing_validation.validation_methodology.pilot_execution_tests.glass_safety.false_negative_rate" "$FNR"
fi

# Section 5: Pilot Test Results - School Access
if [ -f "$PILOT_DATA_DIR/school_access_test_results.json" ]; then
    echo "Updating Section 5: School access tests..."
    SCHOOL_TESTS=$(jq -r '.test_count' "$PILOT_DATA_DIR/school_access_test_results.json")
    BIOMETRIC_MATCH=$(jq -r '.biometric_match_rate' "$PILOT_DATA_DIR/school_access_test_results.json")
    APPEAL_RATE=$(jq -r '.rejection_appeal_rate' "$PILOT_DATA_DIR/school_access_test_results.json")

    update_json "$OUTPUT_FILE" "section_5_testing_validation.validation_methodology.pilot_execution_tests.school_access.test_cases" "$SCHOOL_TESTS"
    update_json "$OUTPUT_FILE" "section_5_testing_validation.validation_methodology.pilot_execution_tests.school_access.biometric_match_rate" "$BIOMETRIC_MATCH"
    update_json "$OUTPUT_FILE" "section_5_testing_validation.validation_methodology.pilot_execution_tests.school_access.rejection_appeal_rate" "$APPEAL_RATE"
fi

# Section 7: Data Handling - pgvector Latency
if [ -f "$PILOT_DATA_DIR/pgvector_benchmark.json" ]; then
    echo "Updating Section 7: pgvector latency benchmark..."
    PGVECTOR_LATENCY=$(jq -r '.query_latency_ms' "$PILOT_DATA_DIR/pgvector_benchmark.json")
    update_json "$OUTPUT_FILE" "section_7_data_handling.data_residency.pgvector_config.query_latency_sla" "<${PGVECTOR_LATENCY}ms (actual)"
fi

# Section 9: Documentation Trail - Proof Artifacts
if [ -f "$PILOT_DATA_DIR/proof_artifacts.json" ]; then
    echo "Updating Section 9: Proof artifacts..."
    for ARTIFACT in artifact_1_can_i_run artifact_2_free_token artifact_3_is_agentic artifact_4_agentacct artifact_5_unlazy artifact_6_ragas artifact_7_ap2_ledger; do
        ARTIFACT_STATUS=$(jq -r ".$ARTIFACT.status // \"TBD\"" "$PILOT_DATA_DIR/proof_artifacts.json")
        ARTIFACT_FILE=$(jq -r ".$ARTIFACT.file_location // \"TBD\"" "$PILOT_DATA_DIR/proof_artifacts.json")

        update_json "$OUTPUT_FILE" "section_9_documentation_trail.proof_artifacts.$ARTIFACT.status" "$ARTIFACT_STATUS"
        update_json "$OUTPUT_FILE" "section_9_documentation_trail.proof_artifacts.$ARTIFACT.file_location" "$ARTIFACT_FILE"
    done
fi

# Compliance Checklist Updates
if [ -f "$PILOT_DATA_DIR/compliance_status.json" ]; then
    echo "Updating compliance checklist..."

    ARTICLE_50_STATUS=$(jq -r '.article_50.status // "PENDING"' "$PILOT_DATA_DIR/compliance_status.json")
    ARTICLE_13_STATUS=$(jq -r '.article_13.status // "PENDING"' "$PILOT_DATA_DIR/compliance_status.json")
    ARTICLE_6_STATUS=$(jq -r '.article_6.status // "PENDING"' "$PILOT_DATA_DIR/compliance_status.json")
    GDPR_STATUS=$(jq -r '.gdpr.status // "PENDING"' "$PILOT_DATA_DIR/compliance_status.json")

    update_json "$OUTPUT_FILE" "compliance_checklist.article_50.technical_documentation" "$ARTICLE_50_STATUS"
    update_json "$OUTPUT_FILE" "compliance_checklist.article_13.transparency_requirements" "$ARTICLE_13_STATUS"
    update_json "$OUTPUT_FILE" "compliance_checklist.article_6.conformity_assessment_procedure" "$ARTICLE_6_STATUS"
    update_json "$OUTPUT_FILE" "compliance_checklist.gdpr_compliance.data_subject_rights_implementation" "$GDPR_STATUS"
fi

# Set export ready if all critical sections populated
echo ""
echo "Verifying population completeness..."
MISSING_FIELDS=$(jq -r 'paths(select(. == "TBD")) | join(".")' "$OUTPUT_FILE" | wc -l)

if [ "$MISSING_FIELDS" -eq 0 ]; then
    echo "✓ All sections populated. Setting pdf_export_ready=true"
    update_json "$OUTPUT_FILE" "metadata.pdf_export_ready" "true"
    echo ""
    echo "SUCCESS: Annex IV dossier ready for PDF export + KMS signing"
    echo "Next steps:"
    echo "  1. Verify JSON syntax: jq . $OUTPUT_FILE"
    echo "  2. Generate PDF: python3 json_to_pdf.py $OUTPUT_FILE"
    echo "  3. Sign with KMS: kms_sign_annex_iv.sh $OUTPUT_FILE"
    echo "  4. Submit to KARP: romana.cernikova@karp-kv.cz"
else
    echo "⚠ $MISSING_FIELDS fields still marked TBD (pending data)"
    echo "Placeholder file saved: $OUTPUT_FILE"
    echo "Populate remaining pilot data before PDF export"
fi

echo "Dossier saved to: $OUTPUT_FILE"
