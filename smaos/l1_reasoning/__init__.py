"""
L1 Reasoning: Policy Router Module

EU AI Act compliance routing for SMAOS pilots:
- Article 50: Transparency (chatbot disclosure)
- Article 6: Risk classification (high-risk AI systems)
- Article 13: Documentation (accuracy, robustness, monitoring)
- Annex III: Prohibited use cases (employment, education, essential services)
- Annex I: High-risk AI systems (safety components)

Pilots:
1. Hotel credit scoring: Article 51 (GPAI) + Annex III (essential service)
2. Glass safety review: Article 6(1) (Annex I - safety component)
3. School access control: Article 6(2) (Annex III - education)
"""

from .policy_router import PolicyRouter, PolicyRoute

__all__ = ["PolicyRouter", "PolicyRoute"]
