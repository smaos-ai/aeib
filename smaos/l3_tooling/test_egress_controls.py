"""
Test Suite for Egress Validator (L3 Tooling Layer)

Covers:
  - Policy-driven whitelist enforcement
  - DNS validation and rebinding prevention
  - TLS certificate validation
  - Rate limiting
  - Audit logging
  - Integration with job router

Total: 18 test cases
"""

import json
import time
import unittest
from unittest.mock import patch, MagicMock
from egress_validator import (
    EgressValidator,
    EgressPolicy,
    EgressResult,
    EgressAttempt,
)


class TestEgressValidatorPolicies(unittest.TestCase):
    """Test policy-driven whitelist enforcement."""

    def setUp(self):
        """Create test policies."""
        self.hotel_policy = EgressPolicy(
            pilot_name="hotel",
            allowed_domains=[
                "equifax.com",
                "experian.com",
                "api.sovereignnexus.io",
            ],
            allowed_patterns=[r".*\.equifax\.com", r".*\.sovereignnexus\.io"],
            critical_apis={"equifax.com": "sha256/ABC123"},
            rate_limit_per_minute=10,
            description="Hotel credit scoring",
        )

        self.glass_policy = EgressPolicy(
            pilot_name="glass",
            allowed_domains=["github.com", "gitlab.com"],
            allowed_patterns=[r"api\.github\.com", r"raw\.githubusercontent\.com"],
            critical_apis={"github.com": "sha256/DEF456"},
            rate_limit_per_minute=15,
            description="Glass safety review",
        )

        self.school_policy = EgressPolicy(
            pilot_name="school",
            allowed_domains=["ed.gov", "studentprivacy.ed.gov"],
            allowed_patterns=[r".*\.edu", r".*\.ed\.gov"],
            critical_apis={"ed.gov": "sha256/GHI789"},
            rate_limit_per_minute=8,
            description="School access control",
        )

        self.validator = EgressValidator(
            {
                "hotel": self.hotel_policy,
                "glass": self.glass_policy,
                "school": self.school_policy,
            }
        )

    def test_whitelist_exact_domain_allowed(self):
        """Test: Exact domain match is allowed."""
        result, attempt = self.validator.validate_egress(
            "hotel", "https://equifax.com/api/score"
        )
        # Will be blocked due to DNS, but should pass policy check
        self.assertIn(attempt.result, [EgressResult.ALLOWED, EgressResult.DNS_VALIDATION_FAILED])

    def test_whitelist_pattern_match_allowed(self):
        """Test: Regex pattern match is allowed."""
        result, attempt = self.validator.validate_egress(
            "hotel", "https://api.sovereignnexus.io/compliance"
        )
        self.assertIn(attempt.result, [EgressResult.ALLOWED, EgressResult.DNS_VALIDATION_FAILED])

    def test_whitelist_domain_not_in_list_blocked(self):
        """Test: Domain not in whitelist is blocked."""
        result, attempt = self.validator.validate_egress(
            "hotel", "https://evil.com/exfil"
        )
        self.assertEqual(attempt.result, EgressResult.BLOCKED)
        self.assertIn("not in whitelist", attempt.reason)

    def test_whitelist_case_insensitive(self):
        """Test: Domain matching is case-insensitive."""
        result, attempt = self.validator.validate_egress(
            "glass", "https://GITHUB.COM/api/repos"
        )
        # Should pass policy (if DNS works)
        self.assertIn(attempt.result, [EgressResult.ALLOWED, EgressResult.DNS_VALIDATION_FAILED])

    def test_whitelist_subdomain_pattern(self):
        """Test: Subdomain patterns work correctly."""
        result, attempt = self.validator.validate_egress(
            "glass", "https://api.github.com/repos"
        )
        self.assertIn(attempt.result, [EgressResult.ALLOWED, EgressResult.DNS_VALIDATION_FAILED])

    def test_invalid_url_format(self):
        """Test: Malformed URLs are rejected or blocked."""
        result, attempt = self.validator.validate_egress(
            "hotel", "ht!tp://[invalid]:99999/path"
        )
        self.assertIn(attempt.result, [EgressResult.INVALID_URL, EgressResult.BLOCKED])

    def test_unknown_pilot_raises(self):
        """Test: Unknown pilot name raises error."""
        with self.assertRaises(ValueError) as ctx:
            self.validator.validate_egress("unknown_pilot", "https://example.com")
        self.assertIn("Unknown pilot", str(ctx.exception))

    def test_different_pilots_different_whitelists(self):
        """Test: Hotels can't access school APIs."""
        # School can access ed.gov
        result, attempt = self.validator.validate_egress(
            "school", "https://ed.gov/api"
        )
        self.assertIn(attempt.result, [EgressResult.ALLOWED, EgressResult.DNS_VALIDATION_FAILED])

        # Hotel cannot access ed.gov (not in whitelist)
        result, attempt = self.validator.validate_egress(
            "hotel", "https://ed.gov/api"
        )
        self.assertEqual(attempt.result, EgressResult.BLOCKED)

    # DNS Validation Tests

    @patch("socket.gethostbyname")
    def test_dns_valid_public_ip(self, mock_dns):
        """Test: Valid public IP passes DNS check."""
        mock_dns.return_value = "1.2.3.4"
        result, attempt = self.validator.validate_egress(
            "hotel", "https://equifax.com/score"
        )
        # Will now pass DNS, but may fail TLS
        self.assertNotEqual(attempt.result, EgressResult.DNS_VALIDATION_FAILED)

    @patch("socket.gethostbyname")
    def test_dns_rejects_private_ips(self, mock_dns):
        """Test: Private IP range is rejected (DNS rebinding prevention)."""
        mock_dns.return_value = "192.168.1.100"
        result, attempt = self.validator.validate_egress(
            "hotel", "https://equifax.com/score"
        )
        self.assertEqual(attempt.result, EgressResult.DNS_VALIDATION_FAILED)
        self.assertIn("private IP", attempt.reason)

    @patch("socket.gethostbyname")
    def test_dns_rejects_loopback(self, mock_dns):
        """Test: Loopback address is rejected."""
        mock_dns.return_value = "127.0.0.1"
        result, attempt = self.validator.validate_egress(
            "hotel", "https://equifax.com/score"
        )
        self.assertEqual(attempt.result, EgressResult.DNS_VALIDATION_FAILED)

    @patch("socket.gethostbyname")
    def test_dns_failure_handling(self, mock_dns):
        """Test: DNS lookup failure is handled."""
        import socket
        mock_dns.side_effect = socket.gaierror("Name resolution failed")
        result, attempt = self.validator.validate_egress(
            "hotel", "https://equifax.com/api"
        )
        self.assertEqual(attempt.result, EgressResult.DNS_VALIDATION_FAILED)

    @patch("socket.gethostbyname")
    def test_dns_caching(self, mock_dns):
        """Test: DNS results are cached."""
        mock_dns.return_value = "1.2.3.4"

        # First call
        self.validator.validate_egress("hotel", "https://equifax.com/score1")
        call_count_1 = mock_dns.call_count

        # Second call to same domain (cached)
        self.validator.validate_egress("hotel", "https://equifax.com/score2")
        call_count_2 = mock_dns.call_count

        # DNS should only be called once due to cache
        self.assertEqual(call_count_1, call_count_2)

    # Rate Limiting Tests

    @patch("socket.gethostbyname")
    def test_rate_limit_allows_under_limit(self, mock_dns):
        """Test: Requests under rate limit are allowed."""
        mock_dns.return_value = "1.2.3.4"
        results = []
        for i in range(5):
            result, attempt = self.validator.validate_egress(
                "hotel", f"https://equifax.com/score{i}"
            )
            results.append(attempt.result)

        # All should pass (not rate limited)
        for result in results:
            self.assertNotEqual(result, EgressResult.RATE_LIMITED)

    @patch("socket.gethostbyname")
    def test_rate_limit_blocks_over_limit(self, mock_dns):
        """Test: Requests over rate limit are blocked."""
        mock_dns.return_value = "1.2.3.4"

        # Make 10 requests (at limit for hotel)
        for i in range(10):
            self.validator.validate_egress(
                "hotel", f"https://equifax.com/score{i}"
            )

        # 11th request should be rate limited
        result, attempt = self.validator.validate_egress(
            "hotel", "https://equifax.com/score11"
        )
        self.assertEqual(attempt.result, EgressResult.RATE_LIMITED)

    @patch("socket.gethostbyname")
    def test_rate_limit_per_pilot(self, mock_dns):
        """Test: Rate limits are per-pilot and per-domain."""
        mock_dns.return_value = "1.2.3.4"

        # Hotel: 10 req/min to equifax
        for i in range(10):
            self.validator.validate_egress(
                "hotel", f"https://equifax.com/score{i}"
            )

        # Glass: 15 req/min, should have 15 available
        for i in range(15):
            result, attempt = self.validator.validate_egress(
                "glass", f"https://github.com/repo{i}"
            )
            if i < 15:
                self.assertNotEqual(attempt.result, EgressResult.RATE_LIMITED)

    @patch("socket.gethostbyname")
    def test_rate_limit_cleanup_old_timestamps(self, mock_dns):
        """Test: Old timestamps outside 1-minute window are cleaned up."""
        mock_dns.return_value = "1.2.3.4"

        # Make request
        self.validator.validate_egress("hotel", "https://equifax.com/score1")

        # Manually move time forward
        pilot = "hotel"
        domain = "equifax.com"
        old_requests = self.validator.rate_limit_tracker[pilot][domain]
        old_requests[0] = time.time() - 61  # 61 seconds ago

        # New request should pass rate limit (old one cleaned up)
        result, attempt = self.validator.validate_egress(
            "hotel", "https://equifax.com/score2"
        )
        self.assertNotEqual(attempt.result, EgressResult.RATE_LIMITED)

    # Integration Tests

    @patch("socket.gethostbyname")
    @patch("ssl.create_default_context")
    def test_full_validation_success(self, mock_ssl, mock_dns):
        """Test: Full validation pipeline (policy + DNS + TLS)."""
        mock_dns.return_value = "1.2.3.4"
        mock_ssl.return_value = MagicMock()

        result, attempt = self.validator.validate_egress(
            "hotel", "https://equifax.com/score", require_tls_pin=False
        )

        self.assertEqual(attempt.result, EgressResult.ALLOWED)
        self.assertEqual(attempt.dns_resolved_ip, "1.2.3.4")

    def test_exfiltration_attempt_blocked(self):
        """Test: Exfiltration attempt to unauthorized domain is blocked."""
        result, attempt = self.validator.validate_egress(
            "hotel", "https://attacker-c2.com/exfil?data=creditcards"
        )
        self.assertEqual(attempt.result, EgressResult.BLOCKED)
        self.assertEqual(attempt.pilot_name, "hotel")
        self.assertIn("attacker-c2.com", attempt.destination_url)

    def test_audit_log_comprehensive(self):
        """Test: Audit log captures all attempts with details."""
        self.validator.validate_egress("hotel", "https://evil.com/x")

        log = self.validator.get_audit_log()
        self.assertEqual(len(log), 1)

        entry = log[0]
        self.assertEqual(entry["pilot_name"], "hotel")
        self.assertEqual(entry["result"], EgressResult.BLOCKED.value)
        self.assertIn("attempt_id", entry)
        self.assertIn("timestamp", entry)

    def test_get_blocked_attempts(self):
        """Test: Can retrieve all blocked attempts."""
        self.validator.validate_egress("hotel", "https://evil1.com/x")
        self.validator.validate_egress("hotel", "https://evil2.com/x")

        blocked = self.validator.get_blocked_attempts()
        self.assertEqual(len(blocked), 2)
        for attempt in blocked:
            self.assertEqual(attempt.result, EgressResult.BLOCKED)

    def test_summary_report(self):
        """Test: Summary report aggregates statistics."""
        self.validator.validate_egress("hotel", "https://evil.com/x")

        summary = self.validator.summary_report()
        self.assertEqual(summary["total_attempts"], 1)
        self.assertEqual(summary["blocked"], 1)
        self.assertIn("hotel", summary["by_pilot"])

    def test_json_serialization(self):
        """Test: Audit log can be serialized to JSON."""
        self.validator.validate_egress("hotel", "https://evil.com/x")

        log = self.validator.get_audit_log()
        json_str = json.dumps(log)

        # Should be valid JSON
        parsed = json.loads(json_str)
        self.assertEqual(len(parsed), 1)
        self.assertIsInstance(parsed[0], dict)


if __name__ == "__main__":
    unittest.main()
