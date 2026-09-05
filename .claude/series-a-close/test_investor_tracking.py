"""
TDD Test Suite: Series A Close Execution Tracking
Tests investor meeting accuracy, term sheet validation, closing checklist completeness
"""

import unittest
from datetime import datetime, timedelta
import json
from unittest.mock import patch


class InvestorMeetingTracker:
    """Track investor meetings with sentiment analysis and LOI status"""

    def __init__(self):
        self.meetings = {}
        self.total_target_meetings = 8

    def add_meeting(self, investor_id, investor_name, meeting_date, stage):
        """Record a meeting with investor"""
        self.meetings[investor_id] = {
            "investor_name": investor_name,
            "meeting_date": meeting_date,
            "stage": stage,  # initial / follow_up / term_negotiation / loi
            "notes": "",
            "sentiment": None,  # positive / neutral / negative
            "loi_status": False,
            "term_sheet_received": False,
        }
        return investor_id

    def update_sentiment(self, investor_id, sentiment):
        """Update sentiment (positive/neutral/negative)"""
        if investor_id not in self.meetings:
            raise ValueError(f"Investor {investor_id} not found")
        valid_sentiments = ["positive", "neutral", "negative"]
        if sentiment not in valid_sentiments:
            raise ValueError(f"Invalid sentiment: {sentiment}")
        self.meetings[investor_id]["sentiment"] = sentiment
        return True

    def update_loi_status(self, investor_id, has_loi):
        """Update LOI status"""
        if investor_id not in self.meetings:
            raise ValueError(f"Investor {investor_id} not found")
        self.meetings[investor_id]["loi_status"] = has_loi
        return True

    def get_summary(self):
        """Return summary of all meetings"""
        total = len(self.meetings)
        with_loi = sum(1 for m in self.meetings.values() if m["loi_status"])
        with_term_sheet = sum(1 for m in self.meetings.values() if m["term_sheet_received"])
        positive = sum(1 for m in self.meetings.values() if m["sentiment"] == "positive")

        return {
            "total_meetings": total,
            "meetings_with_loi": with_loi,
            "meetings_with_term_sheet": with_term_sheet,
            "positive_sentiment_count": positive,
            "completion_percentage": (total / self.total_target_meetings) * 100,
        }


class TermSheetComparator:
    """Compare multiple term sheets side-by-side"""

    def __init__(self):
        self.term_sheets = {}
        self.required_fields = [
            "valuation_usd",
            "investment_amount_usd",
            "dilution_percentage",
            "board_seats",
            "liquidation_preference",  # non-participating / 1x / 2x
        ]

    def add_term_sheet(self, investor_id, term_sheet_data):
        """Add a term sheet for comparison"""
        # Validate required fields
        for field in self.required_fields:
            if field not in term_sheet_data:
                raise ValueError(f"Missing required field: {field}")

        # Validate liquidation preference
        valid_prefs = ["non-participating", "1x", "2x"]
        if term_sheet_data["liquidation_preference"] not in valid_prefs:
            raise ValueError(f"Invalid liquidation_preference: {term_sheet_data['liquidation_preference']}")

        self.term_sheets[investor_id] = term_sheet_data
        return True

    def get_comparison(self):
        """Return side-by-side comparison of all term sheets"""
        if not self.term_sheets:
            return {}

        comparison = {}
        for investor_id, terms in self.term_sheets.items():
            comparison[investor_id] = {
                "valuation_usd": terms["valuation_usd"],
                "investment_amount_usd": terms["investment_amount_usd"],
                "dilution_percentage": terms["dilution_percentage"],
                "board_seats": terms["board_seats"],
                "liquidation_preference": terms["liquidation_preference"],
            }

        # Add best/worst on each dimension
        valuations = [t["valuation_usd"] for t in self.term_sheets.values()]
        comparison["_summary"] = {
            "highest_valuation": max(valuations),
            "lowest_valuation": min(valuations),
            "avg_valuation": sum(valuations) / len(valuations),
        }

        return comparison


class ClosingChecklist:
    """Track 25 closing checklist items"""

    CHECKLIST_ITEMS = [
        # Legal (8 items)
        "incorporation_docs_signed",
        "cap_table_verified",
        "ip_assignment_agreements",
        "employment_agreements",
        "option_grants_documented",
        "material_contracts_listed",
        "litigation_search_clean",
        "compliance_certificates",
        # Tax (5 items)
        "tax_id_verified",
        "state_tax_compliance",
        "employee_tax_withholding_set",
        "equity_documentation_for_taxes",
        "audit_ready_books",
        # Funding Mechanics (6 items)
        "wire_instructions_confirmed",
        "escrow_agreement_signed",
        "use_of_proceeds_documented",
        "investor_account_setup",
        "follow_on_rights_documented",
        "registration_rights_agreement",
        # Post-Close (6 items)
        "board_minutes_post_close",
        "cap_table_update_post_close",
        "investor_portal_setup",
        "preferred_stock_issued",
        "stock_ledger_updated",
        "notifications_to_employees",
    ]

    def __init__(self):
        self.completed_items = set()

    def mark_complete(self, item_name):
        """Mark an item as complete"""
        if item_name not in self.CHECKLIST_ITEMS:
            raise ValueError(f"Invalid item: {item_name}")
        self.completed_items.add(item_name)
        return True

    def get_completion_percentage(self):
        """Get % completion (0-100)"""
        return (len(self.completed_items) / len(self.CHECKLIST_ITEMS)) * 100

    def get_remaining_items(self):
        """Get list of incomplete items"""
        return [item for item in self.CHECKLIST_ITEMS if item not in self.completed_items]

    def is_complete(self):
        """Check if all 25 items are done"""
        return len(self.completed_items) == len(self.CHECKLIST_ITEMS)


class ValuationDefense:
    """Calculate and defend valuation multiples"""

    def __init__(self, annual_recurring_revenue):
        """ARR in USD (e.g., 180_000 for €180K)"""
        self.arr = annual_recurring_revenue

    def calculate_valuation(self, multiple):
        """Calculate valuation at given multiple"""
        if multiple < 1:
            raise ValueError("Multiple must be >= 1")
        return self.arr * multiple

    def get_defensible_range(self):
        """Return defensible valuation range (6x-8x ARR)"""
        low = self.calculate_valuation(6)
        high = self.calculate_valuation(8)
        return {
            "min_valuation": low,
            "min_multiple": 6,
            "max_valuation": high,
            "max_multiple": 8,
            "arr": self.arr,
        }

    def justify_multiple(self, proposed_multiple):
        """Return justification for proposed multiple"""
        defensible = self.get_defensible_range()

        if proposed_multiple < 6:
            return {
                "defensible": False,
                "reason": f"{proposed_multiple}x is below market rate (6x-8x for B2B SaaS)",
            }
        elif proposed_multiple <= 8:
            return {
                "defensible": True,
                "reason": f"{proposed_multiple}x is within defensible B2B SaaS range",
            }
        else:
            return {
                "defensible": False,
                "reason": f"{proposed_multiple}x requires >8x justification (growth rate, retention, CAC payback)",
            }


# ============ TESTS ============

class TestInvestorTracking(unittest.TestCase):
    """test_investor_tracking_accuracy"""

    def test_add_and_retrieve_meeting(self):
        """Can add meeting and verify it's stored"""
        tracker = InvestorMeetingTracker()
        investor_id = tracker.add_meeting(
            "accel_001", "Accel Partners", "2026-06-10", "initial"
        )
        self.assertIn(investor_id, tracker.meetings)
        self.assertEqual(tracker.meetings[investor_id]["investor_name"], "Accel Partners")

    def test_sentiment_update(self):
        """Sentiment update validates input"""
        tracker = InvestorMeetingTracker()
        tracker.add_meeting("a16z_001", "a16z", "2026-06-12", "initial")
        tracker.update_sentiment("a16z_001", "positive")
        self.assertEqual(tracker.meetings["a16z_001"]["sentiment"], "positive")

    def test_invalid_sentiment_rejected(self):
        """Invalid sentiment raises ValueError"""
        tracker = InvestorMeetingTracker()
        tracker.add_meeting("test_001", "Test VC", "2026-06-12", "initial")
        with self.assertRaises(ValueError):
            tracker.update_sentiment("test_001", "excited")

    def test_loi_tracking(self):
        """LOI status updates correctly"""
        tracker = InvestorMeetingTracker()
        tracker.add_meeting("investor_001", "Investor A", "2026-06-10", "initial")
        tracker.update_loi_status("investor_001", True)
        self.assertTrue(tracker.meetings["investor_001"]["loi_status"])

    def test_summary_counts_correctly(self):
        """Summary reports accurate counts"""
        tracker = InvestorMeetingTracker()
        tracker.add_meeting("inv_1", "Investor 1", "2026-06-10", "initial")
        tracker.add_meeting("inv_2", "Investor 2", "2026-06-11", "initial")
        tracker.update_sentiment("inv_1", "positive")
        tracker.update_sentiment("inv_2", "neutral")

        summary = tracker.get_summary()
        self.assertEqual(summary["total_meetings"], 2)
        self.assertEqual(summary["positive_sentiment_count"], 1)


class TestTermSheetComparison(unittest.TestCase):
    """test_term_sheet_comparison_valid"""

    def test_add_valid_term_sheet(self):
        """Valid term sheet is accepted"""
        comparator = TermSheetComparator()
        ts = {
            "valuation_usd": 1_080_000,
            "investment_amount_usd": 270_000,
            "dilution_percentage": 20,
            "board_seats": 1,
            "liquidation_preference": "1x",
        }
        result = comparator.add_term_sheet("investor_001", ts)
        self.assertTrue(result)

    def test_missing_required_field_rejected(self):
        """Missing required field raises ValueError"""
        comparator = TermSheetComparator()
        ts = {
            "valuation_usd": 1_080_000,
            "investment_amount_usd": 270_000,
            # Missing: dilution_percentage
            "board_seats": 1,
            "liquidation_preference": "1x",
        }
        with self.assertRaises(ValueError):
            comparator.add_term_sheet("investor_001", ts)

    def test_invalid_liquidation_preference_rejected(self):
        """Invalid liquidation preference raises ValueError"""
        comparator = TermSheetComparator()
        ts = {
            "valuation_usd": 1_080_000,
            "investment_amount_usd": 270_000,
            "dilution_percentage": 20,
            "board_seats": 1,
            "liquidation_preference": "3x",  # Invalid
        }
        with self.assertRaises(ValueError):
            comparator.add_term_sheet("investor_001", ts)

    def test_comparison_calculates_min_max_avg(self):
        """Comparison includes min/max/avg valuation"""
        comparator = TermSheetComparator()
        comparator.add_term_sheet("inv_1", {
            "valuation_usd": 1_000_000,
            "investment_amount_usd": 250_000,
            "dilution_percentage": 20,
            "board_seats": 1,
            "liquidation_preference": "1x",
        })
        comparator.add_term_sheet("inv_2", {
            "valuation_usd": 1_500_000,
            "investment_amount_usd": 300_000,
            "dilution_percentage": 20,
            "board_seats": 1,
            "liquidation_preference": "1x",
        })

        comparison = comparator.get_comparison()
        self.assertEqual(comparison["_summary"]["lowest_valuation"], 1_000_000)
        self.assertEqual(comparison["_summary"]["highest_valuation"], 1_500_000)


class TestClosingChecklist(unittest.TestCase):
    """test_closing_checklist_complete"""

    def test_has_25_items(self):
        """Checklist has exactly 25 items"""
        checklist = ClosingChecklist()
        self.assertEqual(len(checklist.CHECKLIST_ITEMS), 25)

    def test_mark_item_complete(self):
        """Can mark item as complete"""
        checklist = ClosingChecklist()
        result = checklist.mark_complete("cap_table_verified")
        self.assertTrue(result)
        self.assertIn("cap_table_verified", checklist.completed_items)

    def test_invalid_item_rejected(self):
        """Invalid item name raises ValueError"""
        checklist = ClosingChecklist()
        with self.assertRaises(ValueError):
            checklist.mark_complete("nonexistent_item")

    def test_completion_percentage_calculation(self):
        """Completion % calculated correctly"""
        checklist = ClosingChecklist()
        checklist.mark_complete("cap_table_verified")
        checklist.mark_complete("incorporation_docs_signed")
        percentage = checklist.get_completion_percentage()
        expected = (2 / 25) * 100
        self.assertEqual(percentage, expected)

    def test_remaining_items_list(self):
        """get_remaining_items returns incomplete items"""
        checklist = ClosingChecklist()
        checklist.mark_complete("cap_table_verified")
        remaining = checklist.get_remaining_items()
        self.assertEqual(len(remaining), 24)
        self.assertNotIn("cap_table_verified", remaining)

    def test_is_complete_when_all_done(self):
        """is_complete returns True when all 25 items done"""
        checklist = ClosingChecklist()
        for item in checklist.CHECKLIST_ITEMS:
            checklist.mark_complete(item)
        self.assertTrue(checklist.is_complete())

    def test_is_incomplete_when_missing_items(self):
        """is_complete returns False when items missing"""
        checklist = ClosingChecklist()
        for item in checklist.CHECKLIST_ITEMS[:-1]:  # Mark all but last
            checklist.mark_complete(item)
        self.assertFalse(checklist.is_complete())


class TestValuationDefense(unittest.TestCase):
    """test_valuation_multiples_defensible"""

    def test_calculates_valuation_at_6x(self):
        """6x ARR = €1.08B (on €180K ARR)"""
        defense = ValuationDefense(180_000)
        valuation = defense.calculate_valuation(6)
        self.assertEqual(valuation, 1_080_000)

    def test_calculates_valuation_at_8x(self):
        """8x ARR = €1.44B (on €180K ARR)"""
        defense = ValuationDefense(180_000)
        valuation = defense.calculate_valuation(8)
        self.assertEqual(valuation, 1_440_000)

    def test_defensible_range_6x_to_8x(self):
        """Defensible range returns 6x-8x"""
        defense = ValuationDefense(180_000)
        range_data = defense.get_defensible_range()
        self.assertEqual(range_data["min_valuation"], 1_080_000)
        self.assertEqual(range_data["max_valuation"], 1_440_000)
        self.assertEqual(range_data["min_multiple"], 6)
        self.assertEqual(range_data["max_multiple"], 8)

    def test_rejects_below_6x(self):
        """Multiple < 6x is not defensible"""
        defense = ValuationDefense(180_000)
        result = defense.justify_multiple(5)
        self.assertFalse(result["defensible"])
        self.assertIn("below market rate", result["reason"])

    def test_accepts_6x_to_8x(self):
        """Multiple in 6x-8x range is defensible"""
        defense = ValuationDefense(180_000)
        result = defense.justify_multiple(7)
        self.assertTrue(result["defensible"])

    def test_rejects_above_8x(self):
        """Multiple > 8x requires justification"""
        defense = ValuationDefense(180_000)
        result = defense.justify_multiple(10)
        self.assertFalse(result["defensible"])
        self.assertIn("requires >8x justification", result["reason"])


if __name__ == "__main__":
    unittest.main()
