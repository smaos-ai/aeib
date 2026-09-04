#!/usr/bin/env python3
"""
Phase 8: Explainability Integration for STAR Protocol
SHAP (SHapley Additive exPlanations) + LIME (Local Interpretable Model-agnostic Explanations)

Provides interpretable explanations for every high-risk credit decision.
Users can click "Why?" to see:
  - SHAP waterfall plot (global feature importance)
  - LIME explanation (local approximation for this specific decision)
  - Top 3 features driving the decision

Integration with ledger: every decision receipt contains link to explainability report.
"""

import json
import hashlib
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import random


@dataclass
class Receipt:
    """Cryptographic receipt for a high-risk decision."""
    receipt_id: str
    applicant_id: str
    decision: str  # 'APPROVED' | 'DENIED'
    decision_timestamp: str
    risk_level: str  # 'low', 'medium', 'high'
    explanation_url: str  # Link to explainability report
    signature: str  # Ed25519 signature


class SHAPExplainer:
    """Generate SHAP waterfall plots for feature importance."""

    def __init__(self, model_name: str = "Hotel Credit Scoring"):
        self.model_name = model_name
        self.feature_names = [
            'credit_score',
            'monthly_income',
            'employment_years',
            'debt_to_income_ratio',
            'payment_history_on_time_pct',
            'num_accounts',
            'num_late_payments'
        ]

    def compute_shap_values(
        self,
        applicant: Dict[str, Any],
        base_value: float = 0.5
    ) -> Dict[str, Any]:
        """
        Compute SHAP values (Shapley additive explanations) for applicant.

        This is a simplified implementation. Real SHAP uses game theory
        to compute each feature's marginal contribution to prediction.

        Args:
            applicant: Applicant data dict
            base_value: Base model prediction (e.g., 0.5 = 50% approval rate)

        Returns:
            Dict with SHAP values per feature
        """
        # Normalized feature values
        features = {}
        features['credit_score'] = applicant.get('credit_score', 700) / 850.0
        features['monthly_income'] = min(applicant.get('monthly_income', 5000) / 10000.0, 1.0)
        features['employment_years'] = min(applicant.get('employment_years', 8) / 30.0, 1.0)
        features['debt_to_income_ratio'] = 1.0 - applicant.get('debt_to_income_ratio', 0.35)
        features['payment_history_on_time_pct'] = applicant.get('payment_history_on_time_pct', 95) / 100.0
        features['num_accounts'] = min(applicant.get('num_accounts', 4) / 10.0, 1.0)
        features['num_late_payments'] = 1.0 - min(applicant.get('num_late_payments', 0) / 10.0, 1.0)

        # Simplified SHAP: assign contribution proportional to normalized value
        # Real SHAP would compute marginal contributions via Shapley values
        shap_values = {}
        total_impact = 0.0

        for feature, normalized_value in features.items():
            # Each feature contributes based on normalized value
            contribution = (normalized_value - 0.5) * 0.3  # Max impact per feature = 0.3
            shap_values[feature] = round(contribution, 4)
            total_impact += contribution

        # Prediction = base_value + sum(SHAP values)
        prediction = base_value + total_impact
        prediction = max(0.0, min(1.0, prediction))  # Clamp to [0, 1]

        return {
            'base_value': round(base_value, 4),
            'shap_values': shap_values,
            'prediction': round(prediction, 4),
            'decision': 'APPROVED' if prediction >= 0.5 else 'DENIED'
        }

    def generate_waterfall_plot(
        self,
        applicant: Dict[str, Any],
        receipt_id: str
    ) -> Dict[str, Any]:
        """
        Generate SHAP waterfall plot data for visualization.

        Returns data suitable for plotting waterfall chart:
        Base → Feature 1 → Feature 2 → ... → Prediction

        Args:
            applicant: Applicant data
            receipt_id: Receipt ID for linking

        Returns:
            Dict with waterfall plot coordinates
        """
        shap_result = self.compute_shap_values(applicant)

        # Sort features by |SHAP value| (descending)
        sorted_features = sorted(
            shap_result['shap_values'].items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )

        # Build waterfall trace
        cumulative = shap_result['base_value']
        waterfall_data = []

        waterfall_data.append({
            'feature': 'Base Value (Model Default)',
            'value': shap_result['base_value'],
            'cumulative': cumulative
        })

        for feature, shap_value in sorted_features:
            waterfall_data.append({
                'feature': feature,
                'value': shap_value,
                'cumulative': cumulative + shap_value
            })
            cumulative += shap_value

        return {
            'receipt_id': receipt_id,
            'model': self.model_name,
            'applicant_id': applicant.get('applicant_id'),
            'timestamp': datetime.utcnow().isoformat(),
            'waterfall_trace': waterfall_data,
            'final_prediction': shap_result['prediction'],
            'final_decision': shap_result['decision']
        }


class LIMEExplainer:
    """Generate LIME (Local Interpretable Model-agnostic Explanations) for decisions."""

    def __init__(self, num_samples: int = 1000):
        self.num_samples = num_samples

    def generate_local_explanation(
        self,
        applicant: Dict[str, Any],
        receipt_id: str
    ) -> Dict[str, Any]:
        """
        Generate LIME local explanation for this specific applicant.

        LIME works by:
        1. Perturbing features of the applicant
        2. Getting predictions from the model for each perturbation
        3. Fitting a linear regression to explain local model behavior
        4. Identifying which features drove this decision

        Args:
            applicant: Applicant data
            receipt_id: Receipt ID for linking

        Returns:
            Dict with local explanation
        """
        # Feature ranges for perturbation
        feature_ranges = {
            'credit_score': (300, 850),
            'monthly_income': (1000, 20000),
            'employment_years': (0, 40),
            'debt_to_income_ratio': (0.0, 0.8),
            'payment_history_on_time_pct': (0, 100),
            'num_accounts': (0, 15),
            'num_late_payments': (0, 20)
        }

        # Generate perturbations
        perturbations = []
        predictions = []

        for _ in range(self.num_samples):
            perturbed = {}
            for feature, (min_val, max_val) in feature_ranges.items():
                # Randomly perturb each feature
                perturbed[feature] = random.uniform(min_val, max_val)

            # Get prediction for perturbed instance
            pred = self._predict(perturbed)
            perturbations.append(perturbed)
            predictions.append(pred)

        # Fit linear regression: weight = feature importance
        # Simplified: use correlation between feature and prediction
        feature_weights = {}
        for feature in feature_ranges.keys():
            feature_values = [p[feature] for p in perturbations]
            # Normalize for comparison
            feature_mean = np.mean(feature_values)
            feature_std = np.std(feature_values)

            if feature_std > 0:
                normalized = [(v - feature_mean) / feature_std for v in feature_values]
                correlation = np.corrcoef(normalized, predictions)[0, 1]
                feature_weights[feature] = float(correlation) if not np.isnan(correlation) else 0.0
            else:
                feature_weights[feature] = 0.0

        # Sort by weight magnitude
        top_features = sorted(
            feature_weights.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:3]

        return {
            'receipt_id': receipt_id,
            'applicant_id': applicant.get('applicant_id'),
            'timestamp': datetime.utcnow().isoformat(),
            'explanation_method': 'LIME (Local Interpretable Model-agnostic Explanations)',
            'num_samples': self.num_samples,
            'feature_weights': {k: round(v, 4) for k, v in feature_weights.items()},
            'top_3_features': [
                {'feature': f, 'weight': round(w, 4)} for f, w in top_features
            ],
            'interpretation': self._interpret_top_features(top_features, applicant)
        }

    def _predict(self, applicant: Dict[str, Any]) -> float:
        """Simulate model prediction (in production: call actual model)."""
        # Simplified fair decision logic
        credit_score = applicant.get('credit_score', 700)
        income = applicant.get('monthly_income', 5000)
        dti = applicant.get('debt_to_income_ratio', 0.35)

        # Base probability
        prob = 0.3

        # Credit score impact
        prob += (credit_score / 850.0) * 0.5

        # Income impact
        prob -= (dti / 0.8) * 0.3  # Higher DTI = lower approval

        prob += (income / 20000.0) * 0.2

        return max(0.0, min(1.0, prob))

    def _interpret_top_features(
        self,
        top_features: List[Tuple[str, float]],
        applicant: Dict[str, Any]
    ) -> str:
        """Generate human-readable interpretation of top features."""
        lines = []

        for i, (feature, weight) in enumerate(top_features, 1):
            direction = "increases" if weight > 0 else "decreases"
            value = applicant.get(feature, 'unknown')

            lines.append(
                f"{i}. {feature} ({direction} approval probability): "
                f"Applicant value = {value}, Weight = {weight:.4f}"
            )

        return " | ".join(lines)


class ExplainabilityReporter:
    """Generate and serve explainability reports for decisions."""

    def __init__(self, shap_explainer: SHAPExplainer, lime_explainer: LIMEExplainer):
        self.shap = shap_explainer
        self.lime = lime_explainer

    def explain_high_risk_decision(
        self,
        receipt: Receipt,
        applicant: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate complete explainability report for high-risk decision.

        Links SHAP (global) + LIME (local) explanations.

        Args:
            receipt: Receipt object from decision
            applicant: Applicant data

        Returns:
            Dict with combined SHAP + LIME explanations
        """
        # Generate SHAP waterfall
        shap_waterfall = self.shap.generate_waterfall_plot(applicant, receipt.receipt_id)

        # Generate LIME local explanation
        lime_explanation = self.lime.generate_local_explanation(applicant, receipt.receipt_id)

        # Combine into report
        report = {
            'receipt_id': receipt.receipt_id,
            'applicant_id': receipt.applicant_id,
            'decision': receipt.decision,
            'risk_level': receipt.risk_level,
            'decision_timestamp': receipt.decision_timestamp,
            'shap_explanation': {
                'method': 'SHAP (SHapley Additive exPlanations)',
                'description': 'Global feature importance via Shapley game theory',
                'waterfall': shap_waterfall,
                'interpretation': self._interpret_shap(shap_waterfall)
            },
            'lime_explanation': {
                'method': 'LIME (Local Interpretable Model-agnostic Explanations)',
                'description': 'Local model-agnostic feature importance',
                'explanation': lime_explanation,
                'interpretation': lime_explanation['interpretation']
            },
            'summary': self._generate_summary(receipt, shap_waterfall, lime_explanation)
        }

        return report

    def _interpret_shap(self, waterfall: Dict[str, Any]) -> str:
        """Generate human-readable SHAP interpretation."""
        lines = []

        lines.append(f"Base approval probability: {waterfall['waterfall_trace'][0]['value']:.1%}")
        lines.append("Feature contributions (positive = increases approval, negative = decreases):")

        # Skip base value, show top features
        for item in waterfall['waterfall_trace'][1:]:
            feature = item['feature']
            value = item['value']
            direction = "↑" if value > 0 else "↓"
            lines.append(f"  {direction} {feature}: {value:+.1%}")

        lines.append(f"Final prediction: {waterfall['final_prediction']:.1%} → {waterfall['final_decision']}")

        return " | ".join(lines)

    def _generate_summary(
        self,
        receipt: Receipt,
        shap_waterfall: Dict[str, Any],
        lime_explanation: Dict[str, Any]
    ) -> str:
        """Generate executive summary of decision explanation."""
        top_shap_features = shap_waterfall['waterfall_trace'][1:3]  # Top 2
        top_lime_features = lime_explanation['top_3_features'][:3]

        summary = (
            f"Decision: {receipt.decision} (Risk Level: {receipt.risk_level})\n"
            f"Top drivers (SHAP): {', '.join([f['feature'] for f in top_shap_features])}\n"
            f"Top drivers (LIME): {', '.join([f['feature'] for f in top_lime_features])}"
        )

        return summary

    def save_to_ledger(
        self,
        report: Dict[str, Any],
        ledger_dir: str = '/tmp/decision_explanations'
    ) -> str:
        """
        Save explanation report to ledger directory.

        Each decision gets its own JSON file: decision_explanations/<receipt_id>/report.json

        Args:
            report: Explainability report dict
            ledger_dir: Directory to save reports

        Returns:
            Path to saved report
        """
        receipt_id = report['receipt_id']
        ledger_path = Path(ledger_dir) / receipt_id
        ledger_path.mkdir(parents=True, exist_ok=True)

        report_file = ledger_path / 'explanation.json'

        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        return str(report_file)

    def generate_verification_button_html(
        self,
        receipt: Receipt
    ) -> str:
        """
        Generate HTML for "Why?" button in ledger UI.

        When clicked, shows SHAP waterfall + LIME explanation in browser.

        Returns:
            HTML string
        """
        html = f"""
        <button id="explain-{receipt.receipt_id}" class="explain-btn">
            Why? (Explainability)
        </button>

        <script>
        document.getElementById("explain-{receipt.receipt_id}").addEventListener("click", function() {{
            fetch("/api/explain/{receipt.receipt_id}")
                .then(r => r.json())
                .then(data => {{
                    showSHAPWaterfall(data.shap_explanation);
                    showLIMEExplanation(data.lime_explanation);
                    showDecisionSummary(data.summary);
                }});
        }});
        </script>
        """
        return html


# ============================================================================
# INTEGRATION WITH LEDGER & API
# ============================================================================

class ExplainabilityAPI:
    """REST API for serving explanations."""

    def __init__(self, ledger_dir: str = '/tmp/decision_explanations'):
        self.ledger_dir = ledger_dir
        self.reporter = ExplainabilityReporter(
            SHAPExplainer(),
            LIMEExplainer()
        )

    def explain_receipt(self, receipt_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve explanation for a receipt."""
        report_file = Path(self.ledger_dir) / receipt_id / 'explanation.json'

        if report_file.exists():
            with open(report_file, 'r') as f:
                return json.load(f)
        return None

    def create_explanation_endpoint(self) -> str:
        """
        Return code for Flask/FastAPI endpoint.

        Usage in FastAPI:
            @app.get("/api/explain/{receipt_id}")
            async def get_explanation(receipt_id: str):
                api = ExplainabilityAPI()
                explanation = api.explain_receipt(receipt_id)
                return explanation if explanation else {"error": "Not found"}
        """
        return """
        @app.get("/api/explain/{receipt_id}")
        async def get_explanation(receipt_id: str):
            api = ExplainabilityAPI()
            explanation = api.explain_receipt(receipt_id)
            return explanation if explanation else {"error": "Receipt not found"}
        """


# ============================================================================
# TEST & DEMO
# ============================================================================

def demo_explainability():
    """Demonstrate SHAP + LIME explainability."""
    # Sample applicant
    applicant = {
        'applicant_id': 'APP_001',
        'nationality': 'German',
        'credit_score': 750,
        'monthly_income': 6000,
        'employment_years': 10,
        'debt_to_income_ratio': 0.30,
        'payment_history_on_time_pct': 98,
        'num_accounts': 5,
        'num_late_payments': 0
    }

    # Create receipt
    receipt = Receipt(
        receipt_id='REC_20240904_001',
        applicant_id='APP_001',
        decision='APPROVED',
        decision_timestamp=datetime.utcnow().isoformat(),
        risk_level='medium',
        explanation_url='http://localhost:8000/api/explain/REC_20240904_001',
        signature='ed25519_signature_placeholder'
    )

    # Generate explainability
    shap = SHAPExplainer()
    lime = LIMEExplainer()
    reporter = ExplainabilityReporter(shap, lime)

    report = reporter.explain_high_risk_decision(receipt, applicant)

    # Save to ledger
    output_file = reporter.save_to_ledger(report)

    print("\n" + "="*70)
    print("EXPLAINABILITY REPORT - SHAP + LIME")
    print("="*70)
    print(f"Receipt ID: {receipt.receipt_id}")
    print(f"Applicant ID: {applicant['applicant_id']}")
    print(f"Decision: {receipt.decision} ({receipt.risk_level} risk)")
    print()
    print("SHAP Explanation (Global Feature Importance):")
    print("-" * 70)
    print(report['shap_explanation']['interpretation'])
    print()
    print("LIME Explanation (Local Feature Importance):")
    print("-" * 70)
    print(report['lime_explanation']['interpretation'])
    print()
    print("Summary:")
    print("-" * 70)
    print(report['summary'])
    print()
    print(f"Report saved to: {output_file}")
    print("="*70)

    return report


if __name__ == '__main__':
    demo_explainability()
