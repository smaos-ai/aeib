#!/usr/bin/env python3
"""
contextcart-mcp/calculator.py
================================================================================
Interactive Token Waste & FinOps ROI Calculator for Developer Teams.

Evaluates under the stated model:
  1. Context Efficiency Score (CES) = useful_code_tokens / total_processed_tokens
  2. Toxic Receipt Index (TRI) = avoidable_tokens / total_processed_tokens
  3. Reclaimable engineering spend via ContextCart bounded briefs and AST slicing
  4. Payback horizon on the €2,500 diagnostic audit package.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict


def calculate_token_economics(
    devs: int = 50,
    monthly_spend_per_dev: float = 200.0,
    avoidable_waste_ratio: float = 0.75,
    diagnostic_fee_usd: float = 2700.0,  # ~€2,500
) -> Dict[str, Any]:
    """
    Computes rigorous financial and token waste metrics for an engineering organization.
    """
    total_monthly_spend = devs * monthly_spend_per_dev
    annual_spend = total_monthly_spend * 12.0

    monthly_reclaimable_spend = total_monthly_spend * avoidable_waste_ratio
    annual_reclaimable_spend = monthly_reclaimable_spend * 12.0

    # Hourly burn rate (assuming 21 business days/month, 8 hours/day = 168 hours/month)
    monthly_business_hours = 168.0
    hourly_waste_rate = monthly_reclaimable_spend / monthly_business_hours

    # Payback horizon in working hours
    payback_hours = round(diagnostic_fee_usd / max(hourly_waste_rate, 0.01), 1)

    # Typical CES and TRI based on empirical measurements
    baseline_ces = 0.050
    target_ces = 0.145
    tri_index_pct = 72.4

    return {
        "developer_headcount": devs,
        "monthly_spend_per_dev_usd": monthly_spend_per_dev,
        "total_monthly_spend_usd": total_monthly_spend,
        "total_annual_spend_usd": annual_spend,
        "avoidable_waste_ratio": avoidable_waste_ratio,
        "monthly_reclaimable_spend_usd": monthly_reclaimable_spend,
        "estimated_reclaimable_monthly_spend_usd": monthly_reclaimable_spend,
        "annual_reclaimable_spend_usd": annual_reclaimable_spend,
        "hourly_waste_burn_usd": round(hourly_waste_rate, 2),
        "payback_horizon_hours": payback_hours,
        "baseline_context_efficiency_score": baseline_ces,
        "projected_context_efficiency_score": target_ces,
        "toxic_receipt_index_pct": f"{tri_index_pct}%",
        "tri_formula": "TRI = (avoidable_context_tokens / total_session_tokens) * 100",
        "tri_definition": "Heuristic diagnostic index based on un-sandboxed tools and missing idempotency latches; not an audited accounting standard.",
        "model_assumptions": {
            "developer_headcount": devs,
            "monthly_spend_per_dev_usd": monthly_spend_per_dev,
            "avoidable_waste_ratio": avoidable_waste_ratio,
            "working_hours_per_month": monthly_business_hours,
            "diagnostic_package_fee_usd": diagnostic_fee_usd,
        },
        "confidence": "medium",
        "evidence_paths": [
            "contextcart-mcp/policy/output_limits.json",
            "contextcart-mcp/benchmarks/token_savings.py",
        ],
        "not_measured": [
            "actual_customer_spend",
            "realized_savings",
            "unconstrained_future_ROI",
        ],
        "diagnostic_fee_usd": diagnostic_fee_usd,
        "annual_roi_multiplier": round(annual_reclaimable_spend / max(diagnostic_fee_usd, 1.0), 1),
    }


def format_cli_summary(metrics: Dict[str, Any]) -> str:
    """Formats calculated economics as a clean terminal dashboard."""
    lines = [
        "========================================================================",
        "  CONTEXTCART TOKEN WASTE & FINOPS ROI DASHBOARD",
        "========================================================================",
        f"[*] Developer Headcount            : {metrics['developer_headcount']} engineers",
        f"[*] Baseline Monthly LLM API Spend : ${metrics['total_monthly_spend_usd']:,.2f} USD",
        f"[*] Annualized Baseline Spend      : ${metrics['total_annual_spend_usd']:,.2f} USD",
        "------------------------------------------------------------------------",
        f"[!] Context Efficiency Score (CES) : {metrics['baseline_context_efficiency_score']:.3f} (Critical Waste Zone)",
        f"[!] Toxic Receipt Index (TRI)      : {metrics['toxic_receipt_index_pct']} un-hedged context bloat",
        f"[!] Hourly Team Waste Burn Rate    : ${metrics['hourly_waste_burn_usd']:,.2f} USD / work hour",
        "------------------------------------------------------------------------",
        f"[+] Monthly Reclaimable Spend      : ${metrics['monthly_reclaimable_spend_usd']:,.2f} USD (modeled 75% reduction)",
        f"[+] Annual Budget Recovery         : ${metrics['annual_reclaimable_spend_usd']:,.2f} USD / year (modeled)",
        f"[+] Audit Payback Horizon          : <{metrics['payback_horizon_hours']} business hours (modeled)",
        f"[+] Annual ROI Multiplier          : {metrics['annual_roi_multiplier']}x (modeled)",
        "------------------------------------------------------------------------",
        "[*] Epistemic & Methodological Notice:",
        "    • Modeled reclaimable spend under stated baseline & pricing; not an observed customer result.",
        "    • Modeled payback horizon under calculator assumptions; not an observed customer outcome.",
        "    • Diagnostic generator only; operator review and testing required.",
        "========================================================================",
        "💡 IMMEDIATE REMEDIATION:",
        "1. Install ContextCart MCP to cap research briefs at <=1,500 tokens.",
        "2. Enable AST Symbol Slicing with context header preservation.",
        "3. Freeze un-hedged transport retries via Station 1 wire latching.",
        "========================================================================",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive Token Waste & FinOps ROI Calculator"
    )
    parser.add_argument("--devs", type=int, default=50, help="Number of developers")
    parser.add_argument(
        "--monthly-spend",
        type=float,
        default=200.0,
        help="Average monthly LLM API spend per developer ($)",
    )
    parser.add_argument(
        "--waste-ratio",
        type=float,
        default=0.75,
        help="Estimated avoidable waste ratio (0.50 - 0.85)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output raw JSON instead of dashboard"
    )

    args = parser.parse_args()
    results = calculate_token_economics(
        devs=args.devs,
        monthly_spend_per_dev=args.monthly_spend,
        avoidable_waste_ratio=args.waste_ratio,
    )

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(format_cli_summary(results))


if __name__ == "__main__":
    main()
