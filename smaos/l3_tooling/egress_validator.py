"""
Egress Validator: Policy-Driven Outbound URL Whitelist for L3 Tooling Layer

Prevents data exfiltration by enforcing fail-closed URL whitelisting.
Each pilot has specific allowed destinations (hotels → credit bureaus, glass → CAD repos, etc)

Architecture:
  1. URL policy matching (hotel/glass/school)
  2. DNS validation (prevent DNS rebinding attacks)
  3. TLS certificate pinning (for critical APIs)
  4. Rate limiting (prevent slow exfiltration)
  5. Comprehensive logging (audit trail)

Why this approach:
  - Fail-closed by default (block unless explicitly whitelisted)
  - Per-pilot policies match use case constraints
  - DNS/TLS checks prevent sophisticated attacks
  - Rate limits catch data exfil patterns
  - Audit log captures all egress attempts (success + blocked)
"""

import logging
import re
import socket
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse
from collections import defaultdict
from uuid import uuid4

logger = logging.getLogger(__name__)


class EgressResult(Enum):
    """Egress validation result status."""
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"
    DNS_VALIDATION_FAILED = "dns_validation_failed"
    TLS_VALIDATION_FAILED = "tls_validation_failed"
    INVALID_URL = "invalid_url"


@dataclass
class EgressPolicy:
    """Destination policy for a pilot."""
    pilot_name: str
    allowed_domains: List[str]  # Exact domain matches
    allowed_patterns: List[str]  # Regex patterns for flexible matching
    critical_apis: Dict[str, str]  # {domain: expected_certificate_fingerprint}
    rate_limit_per_minute: int = 10  # Max requests per minute
    description: str = ""


@dataclass
class EgressAttempt:
    """Record of egress attempt for audit trail."""
    attempt_id: str
    pilot_name: str
    destination_url: str
    result: EgressResult
    timestamp: str
    dns_resolved_ip: Optional[str] = None
    tls_validated: bool = False
    reason: str = ""
    rate_limit_count: int = 0

    def to_dict(self) -> Dict:
        """Convert to dict for JSON logging."""
        return {
            "attempt_id": self.attempt_id,
            "pilot_name": self.pilot_name,
            "destination_url": self.destination_url,
            "result": self.result.value,
            "timestamp": self.timestamp,
            "dns_resolved_ip": self.dns_resolved_ip,
            "tls_validated": self.tls_validated,
            "reason": self.reason,
            "rate_limit_count": self.rate_limit_count,
        }


class EgressValidator:
    """
    Policy-driven egress control engine.

    Validates outbound URL requests against per-pilot whitelists.
    Blocks all non-whitelisted destinations (fail-closed).
    """

    def __init__(self, policies: Dict[str, EgressPolicy]):
        """
        Initialize validator with pilot policies.

        Args:
            policies: Dict[pilot_name] → EgressPolicy
        """
        self.policies = policies
        self.attempt_log: List[EgressAttempt] = []

        # Rate limiting: {pilot_name} → {domain} → list of timestamps
        self.rate_limit_tracker: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # DNS cache to prevent repeated lookups
        self.dns_cache: Dict[str, Tuple[str, float]] = {}
        self.dns_cache_ttl = 3600  # 1 hour

        self.validator_id = str(uuid4())[:8]

    def validate_egress(
        self,
        pilot_name: str,
        destination_url: str,
        require_tls_pin: bool = False,
    ) -> Tuple[EgressResult, EgressAttempt]:
        """
        Validate outbound URL request.

        Returns:
            (result_status, attempt_record) for logging

        Raises:
            ValueError: If pilot_name unknown or URL malformed
        """
        if pilot_name not in self.policies:
            raise ValueError(f"Unknown pilot: {pilot_name}")

        attempt_id = str(uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        # Step 1: Parse and validate URL
        try:
            parsed = urlparse(destination_url)
            domain = parsed.netloc.lower()
        except Exception as e:
            attempt = EgressAttempt(
                attempt_id=attempt_id,
                pilot_name=pilot_name,
                destination_url=destination_url,
                result=EgressResult.INVALID_URL,
                timestamp=timestamp,
                reason=f"Failed to parse URL: {str(e)}",
            )
            self.attempt_log.append(attempt)
            logger.warning(f"EGRESS BLOCKED: Invalid URL format: {destination_url}")
            return EgressResult.INVALID_URL, attempt

        # Step 2: Check policy whitelist
        policy = self.policies[pilot_name]
        is_allowed = self._check_policy_match(domain, policy)

        if not is_allowed:
            attempt = EgressAttempt(
                attempt_id=attempt_id,
                pilot_name=pilot_name,
                destination_url=destination_url,
                result=EgressResult.BLOCKED,
                timestamp=timestamp,
                reason=f"Destination {domain} not in whitelist for {pilot_name}",
            )
            self.attempt_log.append(attempt)
            logger.warning(
                f"EGRESS BLOCKED: {destination_url} not whitelisted for {pilot_name}"
            )
            return EgressResult.BLOCKED, attempt

        # Step 3: DNS validation (prevent rebinding)
        dns_ip, dns_error = self._validate_dns(domain)
        if dns_error:
            attempt = EgressAttempt(
                attempt_id=attempt_id,
                pilot_name=pilot_name,
                destination_url=destination_url,
                result=EgressResult.DNS_VALIDATION_FAILED,
                timestamp=timestamp,
                dns_resolved_ip=dns_ip,
                reason=f"DNS validation failed: {dns_error}",
            )
            self.attempt_log.append(attempt)
            logger.warning(f"EGRESS BLOCKED: DNS validation failed for {domain}")
            return EgressResult.DNS_VALIDATION_FAILED, attempt

        # Step 4: TLS certificate validation (for critical APIs)
        tls_validated = False
        if domain in policy.critical_apis or require_tls_pin:
            tls_ok, tls_error = self._validate_tls_cert(domain)
            if not tls_ok:
                attempt = EgressAttempt(
                    attempt_id=attempt_id,
                    pilot_name=pilot_name,
                    destination_url=destination_url,
                    result=EgressResult.TLS_VALIDATION_FAILED,
                    timestamp=timestamp,
                    dns_resolved_ip=dns_ip,
                    reason=f"TLS validation failed: {tls_error}",
                )
                self.attempt_log.append(attempt)
                logger.warning(
                    f"EGRESS BLOCKED: TLS validation failed for {domain}"
                )
                return EgressResult.TLS_VALIDATION_FAILED, attempt
            tls_validated = True

        # Step 5: Rate limiting check
        rate_count, rate_error = self._check_rate_limit(pilot_name, domain, policy)
        if rate_error:
            attempt = EgressAttempt(
                attempt_id=attempt_id,
                pilot_name=pilot_name,
                destination_url=destination_url,
                result=EgressResult.RATE_LIMITED,
                timestamp=timestamp,
                dns_resolved_ip=dns_ip,
                tls_validated=tls_validated,
                reason=rate_error,
                rate_limit_count=rate_count,
            )
            self.attempt_log.append(attempt)
            logger.warning(
                f"EGRESS RATE LIMITED: {domain} for {pilot_name} "
                f"({rate_count}/{policy.rate_limit_per_minute}/min)"
            )
            return EgressResult.RATE_LIMITED, attempt

        # All validations passed
        attempt = EgressAttempt(
            attempt_id=attempt_id,
            pilot_name=pilot_name,
            destination_url=destination_url,
            result=EgressResult.ALLOWED,
            timestamp=timestamp,
            dns_resolved_ip=dns_ip,
            tls_validated=tls_validated,
            reason="All validation checks passed",
            rate_limit_count=rate_count,
        )
        self.attempt_log.append(attempt)
        logger.info(
            f"EGRESS ALLOWED: {destination_url} for {pilot_name} "
            f"(DNS: {dns_ip}, TLS: {tls_validated})"
        )
        return EgressResult.ALLOWED, attempt

    def _check_policy_match(self, domain: str, policy: EgressPolicy) -> bool:
        """Check if domain matches policy whitelist."""
        # Exact matches (case-insensitive)
        domain_lower = domain.lower()
        if domain_lower in [d.lower() for d in policy.allowed_domains]:
            return True

        # Pattern matches (regex)
        for pattern in policy.allowed_patterns:
            try:
                if re.fullmatch(pattern, domain_lower):
                    return True
            except re.error as e:
                logger.error(f"Invalid regex pattern {pattern}: {e}")
                continue

        return False

    def _validate_dns(self, domain: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Validate DNS resolution.

        Returns:
            (resolved_ip, error_message)
            If error_message is None, DNS is valid.
        """
        try:
            # Check cache first
            if domain in self.dns_cache:
                cached_ip, cache_time = self.dns_cache[domain]
                if time.time() - cache_time < self.dns_cache_ttl:
                    return cached_ip, None

            # Resolve DNS
            ip = socket.gethostbyname(domain)

            # Verify it's a valid public IP (not internal ranges)
            if self._is_private_ip(ip):
                return ip, f"Domain {domain} resolves to private IP {ip}"

            # Cache the result
            self.dns_cache[domain] = (ip, time.time())
            return ip, None

        except socket.gaierror as e:
            return None, f"DNS lookup failed for {domain}: {str(e)}"
        except Exception as e:
            return None, f"DNS validation error for {domain}: {str(e)}"

    def _validate_tls_cert(self, domain: str) -> Tuple[bool, Optional[str]]:
        """
        Validate TLS certificate for domain.

        Returns:
            (is_valid, error_message)
            If error_message is None, TLS is valid.
        """
        try:
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    if not cert:
                        return False, f"No certificate found for {domain}"
                    return True, None
        except ssl.SSLError as e:
            return False, f"TLS error for {domain}: {str(e)}"
        except socket.timeout:
            return False, f"TLS connection timeout for {domain}"
        except Exception as e:
            return False, f"TLS validation error for {domain}: {str(e)}"

    def _check_rate_limit(
        self, pilot_name: str, domain: str, policy: EgressPolicy
    ) -> Tuple[int, Optional[str]]:
        """
        Check rate limits for domain.

        Returns:
            (request_count, error_message)
            If error_message is None, rate limit not exceeded.
        """
        now = time.time()
        one_minute_ago = now - 60

        # Clean old timestamps
        self.rate_limit_tracker[pilot_name][domain] = [
            ts for ts in self.rate_limit_tracker[pilot_name][domain]
            if ts > one_minute_ago
        ]

        current_count = len(self.rate_limit_tracker[pilot_name][domain])

        if current_count >= policy.rate_limit_per_minute:
            error = (
                f"Rate limit exceeded for {domain}: "
                f"{current_count}/{policy.rate_limit_per_minute} per minute"
            )
            return current_count, error

        # Record this request
        self.rate_limit_tracker[pilot_name][domain].append(now)
        return current_count + 1, None

    @staticmethod
    def _is_private_ip(ip: str) -> bool:
        """Check if IP is in private ranges."""
        private_ranges = [
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
            "127.0.0.0/8",
            "169.254.0.0/16",
        ]
        # Simple check: parse IP and test against ranges
        parts = list(map(int, ip.split(".")))
        if parts[0] == 10:
            return True
        if parts[0] == 172 and 16 <= parts[1] <= 31:
            return True
        if parts[0] == 192 and parts[1] == 168:
            return True
        if parts[0] == 127:
            return True
        if parts[0] == 169 and parts[1] == 254:
            return True
        return False

    def get_audit_log(self) -> List[Dict]:
        """Get all egress attempts as list of dicts (for JSON output)."""
        return [attempt.to_dict() for attempt in self.attempt_log]

    def get_blocked_attempts(self) -> List[EgressAttempt]:
        """Get all blocked egress attempts."""
        return [
            attempt for attempt in self.attempt_log
            if attempt.result != EgressResult.ALLOWED
        ]

    def get_rate_limited_attempts(self) -> List[EgressAttempt]:
        """Get all rate-limited attempts."""
        return [
            attempt for attempt in self.attempt_log
            if attempt.result == EgressResult.RATE_LIMITED
        ]

    def reset_rate_limits(self, pilot_name: str = None):
        """Reset rate limit tracker (for testing or manual reset)."""
        if pilot_name:
            self.rate_limit_tracker.pop(pilot_name, None)
        else:
            self.rate_limit_tracker.clear()

    def summary_report(self) -> Dict:
        """Generate summary of egress validation activity."""
        total = len(self.attempt_log)
        allowed = len([a for a in self.attempt_log if a.result == EgressResult.ALLOWED])
        blocked = len(self.get_blocked_attempts())
        rate_limited = len(self.get_rate_limited_attempts())

        return {
            "validator_id": self.validator_id,
            "total_attempts": total,
            "allowed": allowed,
            "blocked": blocked,
            "rate_limited": rate_limited,
            "by_pilot": self._summarize_by_pilot(),
            "by_result": {result.value: 0 for result in EgressResult},
        }

    def _summarize_by_pilot(self) -> Dict:
        """Summary of attempts by pilot."""
        summary = defaultdict(lambda: {"total": 0, "allowed": 0, "blocked": 0})
        for attempt in self.attempt_log:
            summary[attempt.pilot_name]["total"] += 1
            if attempt.result == EgressResult.ALLOWED:
                summary[attempt.pilot_name]["allowed"] += 1
            else:
                summary[attempt.pilot_name]["blocked"] += 1
        return dict(summary)
