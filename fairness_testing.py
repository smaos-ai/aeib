"""
Stream K: Fairness Testing for Hotel Credit Scoring
EU AI Act Annex III Compliance - Demographic Parity Testing

Implements demographic parity metric (80% threshold requirement) to prevent
credit discrimination across protected characteristics: age, location, nationality.

Classes:
  - FairnessAnalyzer: Core demographic parity calculations
  - SyntheticDataGenerator: Creates 1000+ hotel guest records with demographics
  - FairnessReporter: Generates pass/fail compliance reports
"""

import json
import random
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import statistics


@dataclass
class HotelGuest:
    """Hotel guest record with demographics and credit decision"""
    guest_id: str
    age: int
    location: str  # urban/rural
    nationality: str  # EU/non-EU
    credit_score: int  # 300-850
    transaction_history: int  # past transactions
    approved: bool  # credit decision


class SyntheticDataGenerator:
    """Generate realistic hotel guest dataset for fairness testing"""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.guests: List[HotelGuest] = []

    def generate_dataset(self, n_records: int = 1000) -> List[HotelGuest]:
        """Generate n_records synthetic hotel guest records"""
        self.guests = []

        for i in range(n_records):
            age = random.randint(18, 85)
            location = random.choice(["urban", "rural"])
            nationality = random.choice(["EU", "non-EU"])
            credit_score = random.randint(300, 850)
            transaction_history = random.randint(0, 50)

            # Simulate approval bias: subtle discrimination
            # EU/urban/higher-age get slight approval boost
            approval_prob = self._calculate_approval_prob(
                age, location, nationality, credit_score, transaction_history
            )
            approved = random.random() < approval_prob

            guest = HotelGuest(
                guest_id=f"guest_{i:05d}",
                age=age,
                location=location,
                nationality=nationality,
                credit_score=credit_score,
                transaction_history=transaction_history,
                approved=approved
            )
            self.guests.append(guest)

        return self.guests

    def _calculate_approval_prob(
        self,
        age: int,
        location: str,
        nationality: str,
        credit_score: int,
        transaction_history: int
    ) -> float:
        """Calculate approval probability with embedded bias"""
        # Base approval probability from credit score
        base_prob = 0.3 + (credit_score / 850.0) * 0.5

        # Add discrimination bias (violated later in testing)
        age_bias = 0.0
        if age < 25:  # Youth penalty
            age_bias = -0.05
        elif age > 65:  # Senior penalty
            age_bias = -0.03

        location_bias = -0.02 if location == "rural" else 0.01
        nationality_bias = -0.03 if nationality == "non-EU" else 0.02
        history_boost = min(transaction_history / 50.0, 1.0) * 0.1

        approval_prob = base_prob + age_bias + location_bias + nationality_bias + history_boost
        return max(0.0, min(1.0, approval_prob))

    def save_to_json(self, filepath: str) -> None:
        """Save dataset to JSON file"""
        data = [asdict(guest) for guest in self.guests]
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def load_from_json(self, filepath: str) -> List[HotelGuest]:
        """Load dataset from JSON file"""
        with open(filepath, "r") as f:
            data = json.load(f)
        self.guests = [HotelGuest(**record) for record in data]
        return self.guests


class FairnessAnalyzer:
    """Analyze demographic parity across protected characteristics"""

    DEMOGRAPHIC_PARITY_THRESHOLD = 0.80  # 80% threshold per EU AI Act

    def __init__(self, dataset: List[HotelGuest]):
        self.dataset = dataset
        self.metrics: Dict[str, Any] = {}

    def calculate_demographic_parity(self, characteristic: str) -> Dict[str, float]:
        """
        Calculate demographic parity ratio.

        Metric: selection_rate_min_group / selection_rate_max_group >= 0.8

        Returns dict with:
          - 'ratio': actual ratio (0.0 to 1.0+)
          - 'passes': True if ratio >= 0.8
          - 'groups': selection rates by group
        """
        groups = self._split_by_characteristic(characteristic)
        selection_rates = {}

        for group_name, guests in groups.items():
            if len(guests) == 0:
                selection_rates[group_name] = 0.0
            else:
                approved = sum(1 for g in guests if g.approved)
                selection_rates[group_name] = approved / len(guests)

        min_rate = min(selection_rates.values()) if selection_rates else 0.0
        max_rate = max(selection_rates.values()) if selection_rates else 1.0

        ratio = min_rate / max_rate if max_rate > 0 else 1.0
        passes = ratio >= self.DEMOGRAPHIC_PARITY_THRESHOLD

        return {
            "characteristic": characteristic,
            "ratio": round(ratio, 4),
            "passes": passes,
            "groups": {k: round(v, 4) for k, v in selection_rates.items()},
            "threshold": self.DEMOGRAPHIC_PARITY_THRESHOLD,
            "min_rate": round(min_rate, 4),
            "max_rate": round(max_rate, 4),
            "disparity_pct": round((max_rate - min_rate) * 100, 2)
        }

    def analyze_all_characteristics(self) -> Dict[str, Dict[str, Any]]:
        """Analyze parity for all protected characteristics"""
        characteristics = ["age", "location", "nationality"]
        results = {}

        for char in characteristics:
            results[char] = self.calculate_demographic_parity(char)

        self.metrics = results
        return results

    def get_compliance_status(self) -> Dict[str, Any]:
        """
        Determine overall compliance: all characteristics must pass.

        Returns:
          {
            "compliant": bool,
            "pass_count": int (out of 3),
            "details": {...}
          }
        """
        if not self.metrics:
            self.analyze_all_characteristics()

        passing = sum(1 for m in self.metrics.values() if m["passes"])
        compliant = passing == len(self.metrics)

        return {
            "compliant": compliant,
            "pass_count": passing,
            "total_characteristics": len(self.metrics),
            "details": self.metrics
        }

    def _split_by_characteristic(self, characteristic: str) -> Dict[str, List[HotelGuest]]:
        """Split dataset by characteristic group"""
        groups = {}

        if characteristic == "age":
            groups["youth (<25)"] = [g for g in self.dataset if g.age < 25]
            groups["working-age (25-65)"] = [g for g in self.dataset if 25 <= g.age <= 65]
            groups["senior (>65)"] = [g for g in self.dataset if g.age > 65]

        elif characteristic == "location":
            groups["urban"] = [g for g in self.dataset if g.location == "urban"]
            groups["rural"] = [g for g in self.dataset if g.location == "rural"]

        elif characteristic == "nationality":
            groups["EU"] = [g for g in self.dataset if g.nationality == "EU"]
            groups["non-EU"] = [g for g in self.dataset if g.nationality == "non-EU"]

        return groups

    def get_dataset_stats(self) -> Dict[str, Any]:
        """Get dataset statistics"""
        if not self.dataset:
            return {}

        approved_count = sum(1 for g in self.dataset if g.approved)
        approval_rate = approved_count / len(self.dataset)

        credit_scores = [g.credit_score for g in self.dataset]

        return {
            "total_records": len(self.dataset),
            "approved_count": approved_count,
            "denied_count": len(self.dataset) - approved_count,
            "overall_approval_rate": round(approval_rate, 4),
            "credit_score_mean": round(statistics.mean(credit_scores), 2),
            "credit_score_median": statistics.median(credit_scores),
            "credit_score_stdev": round(statistics.stdev(credit_scores), 2) if len(credit_scores) > 1 else 0.0,
        }


class FairnessReporter:
    """Generate fairness audit reports"""

    def __init__(self, analyzer: FairnessAnalyzer):
        self.analyzer = analyzer

    def generate_json_report(self, filepath: str = None) -> Dict[str, Any]:
        """Generate comprehensive fairness report in JSON format"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "system": "Hotel Credit Scoring Fairness Audit",
            "framework": "EU AI Act Annex III - Demographic Parity",
            "threshold": FairnessAnalyzer.DEMOGRAPHIC_PARITY_THRESHOLD,
            "dataset_stats": self.analyzer.get_dataset_stats(),
            "compliance": self.analyzer.get_compliance_status(),
            "individual_metrics": self.analyzer.metrics,
        }

        if filepath:
            with open(filepath, "w") as f:
                json.dump(report, f, indent=2)

        return report

    def generate_text_report(self) -> str:
        """Generate human-readable fairness report"""
        compliance = self.analyzer.get_compliance_status()

        lines = [
            "=" * 70,
            "HOTEL CREDIT SCORING - FAIRNESS AUDIT REPORT",
            "EU AI Act Annex III Compliance",
            "=" * 70,
            "",
            f"Report Generated: {datetime.now().isoformat()}",
            "",
            "DATASET SUMMARY",
            "-" * 70,
        ]

        stats = self.analyzer.get_dataset_stats()
        lines.extend([
            f"Total Records: {stats['total_records']}",
            f"Approved: {stats['approved_count']} ({stats['overall_approval_rate']:.1%})",
            f"Denied: {stats['denied_count']} ({1 - stats['overall_approval_rate']:.1%})",
            f"Credit Score Mean: {stats['credit_score_mean']}",
            "",
            "COMPLIANCE STATUS",
            "-" * 70,
        ])

        status_text = "PASS" if compliance["compliant"] else "FAIL"
        lines.append(f"Overall Status: {status_text}")
        lines.append(f"Protected Characteristics Passing: {compliance['pass_count']}/{compliance['total_characteristics']}")
        lines.append("")

        lines.append("DEMOGRAPHIC PARITY ANALYSIS")
        lines.append("-" * 70)

        for char, metric in compliance["details"].items():
            pass_text = "PASS" if metric["passes"] else "FAIL"
            lines.extend([
                f"{char.upper()}: {pass_text}",
                f"  Ratio: {metric['ratio']:.4f} (threshold: {metric['threshold']})",
                f"  Min Rate: {metric['min_rate']:.1%}, Max Rate: {metric['max_rate']:.1%}",
                f"  Disparity: {metric['disparity_pct']:.2f}%",
            ])

            for group, rate in metric["groups"].items():
                lines.append(f"    {group}: {rate:.1%}")

            lines.append("")

        lines.extend([
            "RECOMMENDATION",
            "-" * 70,
        ])

        if compliance["compliant"]:
            lines.append("The model PASSES demographic parity testing.")
            lines.append("All protected characteristics meet the 80% fairness threshold.")
        else:
            lines.append("The model FAILS demographic parity testing.")
            lines.append("Review decision logic for discriminatory patterns.")
            failing = [c for c, m in compliance["details"].items() if not m["passes"]]
            lines.append(f"Failing characteristics: {', '.join(failing)}")

        lines.extend([
            "",
            "=" * 70,
        ])

        return "\n".join(lines)

    def print_report(self) -> None:
        """Print fairness report to console"""
        print(self.generate_text_report())


def create_fair_approval_scenario(n_records: int = 1000) -> Tuple[List[HotelGuest], bool]:
    """
    Create scenario where all groups pass 80% parity threshold.
    Returns (dataset, passes_compliance).
    """
    gen = SyntheticDataGenerator(seed=100)
    dataset = gen.generate_dataset(n_records)

    # Force fair outcomes: approve ~60% across all groups
    for guest in dataset:
        guest.approved = random.random() < 0.60

    analyzer = FairnessAnalyzer(dataset)
    compliance = analyzer.get_compliance_status()

    return dataset, compliance["compliant"]


def create_unfair_approval_scenario(n_records: int = 1000) -> Tuple[List[HotelGuest], bool]:
    """
    Create scenario where at least one group fails 80% parity threshold.
    Returns (dataset, passes_compliance).
    """
    gen = SyntheticDataGenerator(seed=101)
    dataset = gen.generate_dataset(n_records)

    # Force unfair outcomes: discriminate against youth and non-EU
    for guest in dataset:
        if guest.age < 25 and guest.nationality == "non-EU":
            # Only 40% approval for youth non-EU
            guest.approved = random.random() < 0.40
        elif guest.age >= 25 and guest.nationality == "EU":
            # 85% approval for working-age EU
            guest.approved = random.random() < 0.85
        else:
            guest.approved = random.random() < 0.65

    analyzer = FairnessAnalyzer(dataset)
    compliance = analyzer.get_compliance_status()

    return dataset, compliance["compliant"]
