"""
Stream K: Fairness Testing for Hotel Credit Scoring
TDD Test Suite - 15+ Tests for Demographic Parity Compliance

Tests Cover:
  - Tests 1-5: Demographic parity metric calculations
  - Tests 6-10: Edge cases (all approved, all denied, single group)
  - Tests 11-15: Integration with L1 policy router
"""

import sys
import json
import pytest
import random
from pathlib import Path

sys.path.insert(0, '/Users/andriileukhin/Documents/SovereignNexus')

from fairness_testing import (
    FairnessAnalyzer,
    SyntheticDataGenerator,
    FairnessReporter,
    HotelGuest,
    create_fair_approval_scenario,
    create_unfair_approval_scenario,
)


# ============================================================================
# TESTS 1-5: Demographic Parity Metric Calculations
# ============================================================================

def test_demographic_parity_age_calculation():
    """Test 1: Demographic parity correctly calculates age disparity"""
    gen = SyntheticDataGenerator(seed=42)
    dataset = gen.generate_dataset(500)

    # Force known outcomes: youth 50%, working-age 80%, senior 70%
    for guest in dataset:
        if guest.age < 25:
            guest.approved = random.random() < 0.50
        elif guest.age <= 65:
            guest.approved = random.random() < 0.80
        else:
            guest.approved = random.random() < 0.70

    analyzer = FairnessAnalyzer(dataset)
    metric = analyzer.calculate_demographic_parity("age")

    assert metric["characteristic"] == "age"
    assert "ratio" in metric
    assert "groups" in metric
    assert isinstance(metric["ratio"], float)
    # Ratio should be min/max = 50/80 = 0.625 (roughly, accounting for randomness)
    assert metric["ratio"] < 0.80  # Should fail 80% threshold


def test_demographic_parity_location_calculation():
    """Test 2: Demographic parity correctly calculates location disparity"""
    gen = SyntheticDataGenerator(seed=43)
    dataset = gen.generate_dataset(500)

    # Force known outcomes: urban 75%, rural 50%
    for guest in dataset:
        if guest.location == "urban":
            guest.approved = random.random() < 0.75
        else:
            guest.approved = random.random() < 0.50

    analyzer = FairnessAnalyzer(dataset)
    metric = analyzer.calculate_demographic_parity("location")

    assert metric["characteristic"] == "location"
    assert metric["ratio"] < 0.80  # Should fail: 50/75 = 0.667
    assert "urban" in metric["groups"]
    assert "rural" in metric["groups"]


def test_demographic_parity_nationality_calculation():
    """Test 3: Demographic parity correctly calculates nationality disparity"""
    gen = SyntheticDataGenerator(seed=44)
    dataset = gen.generate_dataset(500)

    # Force known outcomes: EU 80%, non-EU 55%
    for guest in dataset:
        if guest.nationality == "EU":
            guest.approved = random.random() < 0.80
        else:
            guest.approved = random.random() < 0.55

    analyzer = FairnessAnalyzer(dataset)
    metric = analyzer.calculate_demographic_parity("nationality")

    assert metric["characteristic"] == "nationality"
    assert metric["ratio"] < 0.80  # Should fail: 55/80 = 0.6875
    assert "EU" in metric["groups"]
    assert "non-EU" in metric["groups"]


def test_demographic_parity_passes_threshold():
    """Test 4: Demographic parity passes when ratio >= 0.80"""
    gen = SyntheticDataGenerator(seed=45)
    dataset = gen.generate_dataset(500)

    # Force fair outcomes: all groups at 70% approval
    for guest in dataset:
        guest.approved = random.random() < 0.70

    analyzer = FairnessAnalyzer(dataset)
    metric = analyzer.calculate_demographic_parity("age")

    assert metric["passes"] is True
    assert metric["ratio"] >= 0.80


def test_demographic_parity_ratio_calculation_accuracy():
    """Test 5: Demographic parity ratio calculation is mathematically correct"""
    gen = SyntheticDataGenerator(seed=46)
    dataset = gen.generate_dataset(100)

    # Set precise approval rates: urban 60%, rural 50%
    urban_guests = [g for g in dataset if g.location == "urban"]
    rural_guests = [g for g in dataset if g.location == "rural"]

    for guest in urban_guests:
        guest.approved = True
    # Approve 50% of rural
    for i, guest in enumerate(rural_guests):
        guest.approved = i % 2 == 0

    analyzer = FairnessAnalyzer(dataset)
    metric = analyzer.calculate_demographic_parity("location")

    # urban rate = 100%, rural rate = 50%, ratio = 50/100 = 0.50
    assert metric["min_rate"] == 0.50
    assert metric["max_rate"] == 1.00
    assert metric["ratio"] == 0.50


# ============================================================================
# TESTS 6-10: Edge Cases
# ============================================================================

def test_edge_case_all_approved():
    """Test 6: All guests approved (100% fairness)"""
    gen = SyntheticDataGenerator(seed=47)
    dataset = gen.generate_dataset(100)

    # Approve everyone
    for guest in dataset:
        guest.approved = True

    analyzer = FairnessAnalyzer(dataset)
    metric = analyzer.calculate_demographic_parity("age")

    assert metric["passes"] is True
    assert metric["ratio"] == 1.0  # Perfect parity
    assert all(rate == 1.0 for rate in metric["groups"].values())


def test_edge_case_all_denied():
    """Test 7: All guests denied (100% fairness)"""
    gen = SyntheticDataGenerator(seed=48)
    dataset = gen.generate_dataset(100)

    # Deny everyone
    for guest in dataset:
        guest.approved = False

    analyzer = FairnessAnalyzer(dataset)
    metric = analyzer.calculate_demographic_parity("location")

    assert metric["passes"] is True
    assert metric["ratio"] == 1.0  # Perfect parity
    assert all(rate == 0.0 for rate in metric["groups"].values())


def test_edge_case_empty_group():
    """Test 8: Handles empty demographic groups gracefully"""
    gen = SyntheticDataGenerator(seed=49)
    dataset = gen.generate_dataset(100)

    # Remove all senior guests
    dataset = [g for g in dataset if g.age <= 65]

    analyzer = FairnessAnalyzer(dataset)
    metric = analyzer.calculate_demographic_parity("age")

    # Should not crash, handle zero-length groups
    assert metric["ratio"] >= 0.0
    assert len(metric["groups"]) > 0


def test_edge_case_single_record():
    """Test 9: Handles dataset with single record"""
    gen = SyntheticDataGenerator(seed=50)
    dataset = gen.generate_dataset(1)

    analyzer = FairnessAnalyzer(dataset)
    metric = analyzer.calculate_demographic_parity("age")

    # Should return valid metric
    assert metric["characteristic"] == "age"
    assert isinstance(metric["ratio"], float)


def test_edge_case_extreme_disparity():
    """Test 10: Detects extreme disparity (1% vs 99% approval)"""
    gen = SyntheticDataGenerator(seed=51)
    dataset = gen.generate_dataset(200)

    youth = [g for g in dataset if g.age < 25]
    adults = [g for g in dataset if g.age >= 25]

    # 1% youth approval, 99% adult approval
    for guest in youth:
        guest.approved = random.random() < 0.01
    for guest in adults:
        guest.approved = random.random() < 0.99

    analyzer = FairnessAnalyzer(dataset)
    metric = analyzer.calculate_demographic_parity("age")

    assert metric["passes"] is False
    assert metric["disparity_pct"] > 90  # Huge disparity


# ============================================================================
# TESTS 11-15: Integration & Compliance Scenarios
# ============================================================================

def test_integration_fair_approval_scenario():
    """Test 11: Fair approval scenario passes compliance"""
    dataset, passes = create_fair_approval_scenario(n_records=1000)

    analyzer = FairnessAnalyzer(dataset)
    compliance = analyzer.get_compliance_status()

    assert compliance["compliant"] is True
    assert compliance["pass_count"] == 3  # All 3 characteristics


def test_integration_unfair_approval_scenario():
    """Test 12: Unfair approval scenario fails compliance"""
    dataset, passes = create_unfair_approval_scenario(n_records=1000)

    analyzer = FairnessAnalyzer(dataset)
    compliance = analyzer.get_compliance_status()

    assert compliance["compliant"] is False
    assert compliance["pass_count"] < 3  # At least one fails


def test_integration_all_characteristics_analyzed():
    """Test 13: All protected characteristics are analyzed"""
    gen = SyntheticDataGenerator(seed=52)
    dataset = gen.generate_dataset(500)

    analyzer = FairnessAnalyzer(dataset)
    compliance = analyzer.get_compliance_status()

    assert "age" in compliance["details"]
    assert "location" in compliance["details"]
    assert "nationality" in compliance["details"]


def test_integration_fairness_reporter_generates_report():
    """Test 14: Fairness reporter generates valid JSON report"""
    gen = SyntheticDataGenerator(seed=53)
    dataset = gen.generate_dataset(500)

    analyzer = FairnessAnalyzer(dataset)
    reporter = FairnessReporter(analyzer)

    report = reporter.generate_json_report()

    assert "timestamp" in report
    assert "system" in report
    assert "framework" in report
    assert "dataset_stats" in report
    assert "compliance" in report
    assert "individual_metrics" in report


def test_integration_fairness_reporter_text_report():
    """Test 15: Fairness reporter generates readable text report"""
    gen = SyntheticDataGenerator(seed=54)
    dataset = gen.generate_dataset(500)

    analyzer = FairnessAnalyzer(dataset)
    reporter = FairnessReporter(analyzer)

    text_report = reporter.generate_text_report()

    assert "HOTEL CREDIT SCORING" in text_report
    assert "FAIRNESS AUDIT REPORT" in text_report
    assert "COMPLIANCE STATUS" in text_report
    assert "DEMOGRAPHIC PARITY" in text_report
    assert ("PASS" in text_report or "FAIL" in text_report)


# ============================================================================
# ADDITIONAL TESTS: Data Generation & Persistence
# ============================================================================

def test_synthetic_data_generator_creates_correct_count():
    """Test 16: Synthetic data generator creates requested count"""
    gen = SyntheticDataGenerator(seed=55)
    dataset = gen.generate_dataset(1000)

    assert len(dataset) == 1000
    assert all(isinstance(g, HotelGuest) for g in dataset)


def test_synthetic_data_generator_has_valid_attributes():
    """Test 17: Each guest record has all required attributes"""
    gen = SyntheticDataGenerator(seed=56)
    dataset = gen.generate_dataset(100)

    for guest in dataset:
        assert hasattr(guest, "guest_id")
        assert hasattr(guest, "age")
        assert hasattr(guest, "location")
        assert hasattr(guest, "nationality")
        assert hasattr(guest, "credit_score")
        assert hasattr(guest, "approved")
        assert guest.age >= 18 and guest.age <= 85
        assert guest.location in ["urban", "rural"]
        assert guest.nationality in ["EU", "non-EU"]
        assert guest.credit_score >= 300 and guest.credit_score <= 850


def test_synthetic_data_persistence():
    """Test 18: Synthetic data can be saved and loaded"""
    import tempfile
    import os

    gen = SyntheticDataGenerator(seed=57)
    original_dataset = gen.generate_dataset(100)

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_file = f.name

    try:
        gen.save_to_json(temp_file)

        # Load it back
        gen2 = SyntheticDataGenerator()
        loaded_dataset = gen2.load_from_json(temp_file)

        assert len(loaded_dataset) == len(original_dataset)
        assert loaded_dataset[0].guest_id == original_dataset[0].guest_id
        assert loaded_dataset[0].age == original_dataset[0].age
    finally:
        os.unlink(temp_file)


def test_compliance_threshold_constant():
    """Test 19: Demographic parity threshold is correctly set to 0.80"""
    assert FairnessAnalyzer.DEMOGRAPHIC_PARITY_THRESHOLD == 0.80


def test_dataset_statistics_comprehensive():
    """Test 20: Dataset statistics are comprehensive and accurate"""
    gen = SyntheticDataGenerator(seed=58)
    dataset = gen.generate_dataset(500)

    analyzer = FairnessAnalyzer(dataset)
    stats = analyzer.get_dataset_stats()

    assert stats["total_records"] == 500
    assert stats["approved_count"] + stats["denied_count"] == 500
    assert 0.0 <= stats["overall_approval_rate"] <= 1.0
    assert stats["credit_score_mean"] > 300
    assert stats["credit_score_mean"] < 850
    assert stats["credit_score_stdev"] >= 0


# ============================================================================
# Execution Entry Point (for direct testing)
# ============================================================================

if __name__ == "__main__":
    # Run with: python -m pytest tests/stream_k/test_fairness_hotel.py -v
    pytest.main([__file__, "-v", "--tb=short"])
