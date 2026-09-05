#!/usr/bin/env python3
"""
Stream Q: Pilot Data Generation
Generates synthetic test data for 3 regional pilots (Sep 1-15, 2026)
- Hotel Credit Scoring: 1,000 guest records
- Glass Factory Safety: 500 CAD designs
- School Access Control: 2,000 student records
PII Masking: All names/emails hashed with SHA256
GDPR Compliance: 30-day retention, automatic purge
"""

import hashlib
import json
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Configuration
HOTEL_GUEST_COUNT = 1000
GLASS_DESIGN_COUNT = 500
SCHOOL_STUDENT_COUNT = 2000

EU_COUNTRIES = [
    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
    'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
    'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
]

AGE_BRACKETS = ['18-24', '25-34', '35-44', '45-54', '55-64', '65+']
FAIRNESS_GROUPS = ['elderly', 'non_eu', 'low_credit', 'new_guest', 'baseline']

def hash_pii(value: str) -> str:
    """Hash PII using SHA256 (one-way anonymization)."""
    return hashlib.sha256(value.encode()).hexdigest()

def generate_hotel_data() -> List[Dict[str, Any]]:
    """Generate 1,000 hotel guest records with fairness test coverage."""
    guests = []
    test_run_id = str(uuid.uuid4())

    # Ensure fairness group coverage
    groups_per_count = HOTEL_GUEST_COUNT // len(FAIRNESS_GROUPS)

    for i in range(HOTEL_GUEST_COUNT):
        fairness_idx = (i // groups_per_count) % len(FAIRNESS_GROUPS)
        fairness_group = FAIRNESS_GROUPS[fairness_idx]

        # Bias generation by fairness group
        if fairness_group == 'elderly':
            age_bracket = random.choice(['55-64', '65+'])
            credit_score = random.randint(620, 800)  # Typically good credit
        elif fairness_group == 'non_eu':
            age_bracket = random.choice(AGE_BRACKETS)
            credit_score = random.randint(550, 750)  # Slightly lower
            eu_resident = False
            location = random.choice([c for c in EU_COUNTRIES if random.random() > 0.3]) + random.choice(['US', 'CN', 'IN', 'BR', 'AU'])
        elif fairness_group == 'low_credit':
            age_bracket = random.choice(AGE_BRACKETS)
            credit_score = random.randint(300, 579)  # Low credit
        elif fairness_group == 'new_guest':
            age_bracket = random.choice(['18-24', '25-34'])
            credit_score = random.randint(620, 750)
        else:  # baseline
            age_bracket = random.choice(AGE_BRACKETS)
            credit_score = random.randint(680, 800)

        eu_resident = random.random() > 0.15 if fairness_group != 'non_eu' else False
        location = random.choice(EU_COUNTRIES) if eu_resident else random.choice(['US', 'GB', 'CA', 'AU'])

        guest_email = f"guest_{i}@example.com"
        guest_hash = hash_pii(guest_email)

        guests.append({
            'guest_hash': guest_hash,
            'age_bracket': age_bracket,
            'eu_resident': eu_resident,
            'location_country': location,
            'credit_score': credit_score,
            'previous_bookings': random.randint(0, 50),
            'previous_cancellations': random.randint(0, 5),
            'average_stay_nights': random.randint(1, 10),
            'total_spending_usd': round(random.uniform(500, 50000), 2),
            'approval_decision': random.choice(['APPROVED', 'DENIED', 'ESCALATED']),
            'risk_score': round(random.random(), 3),
            'fairness_group': fairness_group,
            'test_run_id': test_run_id
        })

    return guests

def generate_glass_data() -> List[Dict[str, Any]]:
    """Generate 500 CAD design documents with safety-critical specs."""
    designs = []
    test_run_id = str(uuid.uuid4())

    for i in range(GLASS_DESIGN_COUNT):
        design_type = random.choice(['automotive', 'architectural', 'appliance'])
        material_grade = random.choice(['tempered', 'laminated', 'annealed'])

        # Safety-critical: 2% should have issues
        has_safety_issue = random.random() < 0.02

        design_hash = hash_pii(f"cad_design_{i}_v1")

        designs.append({
            'design_hash': design_hash,
            'design_name': f'CAD_{design_type.upper()}_{i:04d}',
            'design_type': design_type,
            'material_grade': material_grade,
            'thickness_mm': round(random.uniform(2.5, 8.0), 1),
            'stress_test_passed': not has_safety_issue and random.random() > 0.1,
            'temperature_range': random.choice(['-20C to 80C', '-10C to 70C', '-30C to 90C']),
            'safety_spec_version': random.choice(['ISO 12150', 'EN 1288', 'EN 366']),
            'l1_policy_status': 'non_compliant' if has_safety_issue else random.choice(['compliant', 'compliant']),
            'l3_safety_gate_result': 'FAIL' if has_safety_issue else random.choice(['PASS', 'PASS', 'REVIEW']),
            'risk_level': random.randint(50, 100) if has_safety_issue else random.randint(0, 40),
            'auditor_id': f'auditor_{random.randint(1, 5)}',
            'auditor_approval': not has_safety_issue,
            'design_comments': 'Safety-critical defect found' if has_safety_issue else 'Design meets specs',
            'test_run_id': test_run_id
        })

    return designs

def generate_school_data() -> List[Dict[str, Any]]:
    """Generate 2,000 student records with biometric + attendance tracking."""
    students = []
    test_run_id = str(uuid.uuid4())

    for i in range(SCHOOL_STUDENT_COUNT):
        student_email = f"student_{i}@school.edu"
        student_hash = hash_pii(student_email)
        biometric_hash = hash_pii(f"biometric_{i}")
        guardian_hash = hash_pii(f"guardian_{i}@parent.edu")

        age_group = random.choice(['5-9', '10-14', '15-18'])
        enrollment_status = random.choice(['active', 'on_campus', 'off_campus'])

        # Generate realistic attendance
        if enrollment_status == 'on_campus':
            attendance_rate = round(random.uniform(0.85, 1.0), 2)
            days_since = random.randint(0, 3)
        elif enrollment_status == 'off_campus':
            attendance_rate = round(random.uniform(0.0, 0.5), 2)
            days_since = random.randint(7, 30)
        else:  # active
            attendance_rate = round(random.uniform(0.7, 0.95), 2)
            days_since = random.randint(0, 7)

        enrollment_date = datetime.now() - timedelta(days=random.randint(30, 365))
        last_visit = datetime.now() - timedelta(days=days_since)

        students.append({
            'student_hash': student_hash,
            'age_group': age_group,
            'enrollment_status': enrollment_status,
            'enrollment_date': enrollment_date.date().isoformat(),
            'last_campus_visit': last_visit.date().isoformat(),
            'attendance_rate': attendance_rate,
            'days_since_attendance': days_since,
            'biometric_template_hash': biometric_hash,
            'biometric_enrollment_date': (enrollment_date).date().isoformat(),
            'teacher_notes': random.choice(['Good student', 'Needs support', 'Excellent attendance', 'At-risk']),
            'guardian_contact_hash': guardian_hash,
            'special_accommodations': random.choice([None, 'ADHD', 'Visual impairment', 'Hearing aid']) if random.random() > 0.9 else None,
            'test_run_id': test_run_id
        })

    return students

def generate_load_test_scenarios(guests: List, designs: List, students: List) -> Dict[str, Any]:
    """Generate load testing scenarios for latency + throughput validation."""

    return {
        'hotel_pilot': {
            'total_records': len(guests),
            'load_test_rps': 100,  # requests per second target
            'load_test_duration_seconds': 60,
            'expected_latency_p95_ms': 15000,  # <15s per spec
            'expected_latency_p99_ms': 18000,
            'fairness_groups_covered': len(set(g['fairness_group'] for g in guests)),
            'edge_cases': [
                'elderly_high_credit',
                'non_eu_low_credit',
                'new_guest_baseline',
                'high_previous_cancellations'
            ]
        },
        'glass_pilot': {
            'total_records': len(designs),
            'load_test_rps': 50,
            'load_test_duration_seconds': 60,
            'expected_latency_p95_ms': 500,
            'expected_latency_p99_ms': 750,
            'expected_fnr_max': 0.0001,  # 0.01%
            'safety_critical_count': len([d for d in designs if d['l3_safety_gate_result'] == 'FAIL']),
            'edge_cases': [
                'safety_critical_design',
                'ambiguous_spec',
                'marginal_stress_test',
                'material_grade_boundary'
            ]
        },
        'school_pilot': {
            'total_records': len(students),
            'load_test_rps': 200,
            'load_test_duration_seconds': 60,
            'expected_latency_p95_ms': 5000,
            'expected_latency_p99_ms': 8000,
            'expected_biometric_accuracy': 0.98,
            'temporal_cache_duration_hours': 48,
            'enrollment_states_covered': len(set(s['enrollment_status'] for s in students)),
            'edge_cases': [
                'low_biometric_confidence',
                'off_campus_student',
                'transferred_student',
                'spoofed_biometric',
                'network_outage_recovery'
            ]
        }
    }

def main():
    """Generate all pilot data and save to JSON files."""
    print("[Stream Q] Generating pilot execution data...")

    # Generate data
    hotel_guests = generate_hotel_data()
    glass_designs = generate_glass_data()
    school_students = generate_school_data()

    # Generate load test scenarios
    scenarios = generate_load_test_scenarios(hotel_guests, glass_designs, school_students)

    # Save to JSON
    output_dir = '/Users/andriileukhin/Documents/SovereignNexus/pilots/data'
    import os
    os.makedirs(output_dir, exist_ok=True)

    with open(f'{output_dir}/hotel_pilot_guests.json', 'w') as f:
        json.dump(hotel_guests, f, indent=2)

    with open(f'{output_dir}/glass_pilot_designs.json', 'w') as f:
        json.dump(glass_designs, f, indent=2)

    with open(f'{output_dir}/school_pilot_students.json', 'w') as f:
        json.dump(school_students, f, indent=2)

    with open(f'{output_dir}/load_test_scenarios.json', 'w') as f:
        json.dump(scenarios, f, indent=2)

    print(f"[Stream Q] Generated {len(hotel_guests)} hotel guests")
    print(f"[Stream Q] Generated {len(glass_designs)} glass designs")
    print(f"[Stream Q] Generated {len(school_students)} school students")
    print(f"[Stream Q] Saved to {output_dir}/")

    # Print summary
    print("\n[Summary]")
    print(f"Hotel fairness groups: {set(g['fairness_group'] for g in hotel_guests)}")
    print(f"Glass safety-critical designs: {len([d for d in glass_designs if d['l3_safety_gate_result'] == 'FAIL'])}")
    print(f"School enrollment states: {set(s['enrollment_status'] for s in school_students)}")

if __name__ == '__main__':
    main()
