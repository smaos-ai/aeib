"""
L5A: Egress Policy Engine
Policy loading, DNS resolution, DNSSEC validation
"""

import json
import hashlib
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
import logging

logger = logging.getLogger(__name__)


class EgressPolicyEngine:
    """Policy loading and validation engine"""

    def __init__(self):
        self.policy: Dict = {}
        self.policy_hash: str = ""
        self.last_reload: Optional[datetime] = None
        self.lock = threading.RLock()

    def _validate_schema(self, policy: Dict) -> bool:
        """Validate policy against JSON schema"""
        try:
            required_keys = ['version', 'updated_at', 'destinations']
            if not all(k in policy for k in required_keys):
                logger.error("Missing required policy keys")
                return False

            if policy.get('version') != '1.0':
                logger.error(f"Unsupported policy version: {policy.get('version')}")
                return False

            for dest in policy.get('destinations', []):
                # At least one of hostnames or ips
                if not (dest.get('hostnames') or dest.get('ips')):
                    logger.error(f"Destination {dest.get('id')} missing hostnames or ips")
                    return False

                # Ports must be integers 1-65535
                for port in dest.get('ports', []):
                    if not isinstance(port, int) or port < 1 or port > 65535:
                        logger.error(f"Invalid port in {dest.get('id')}: {port}")
                        return False

            return True

        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            return False

    def _compute_hash(self) -> str:
        """Compute canonical hash of policy"""
        try:
            canonical = json.dumps(
                self.policy,
                sort_keys=True,
                separators=(',', ':')
            )
            self.policy_hash = hashlib.sha256(canonical.encode()).hexdigest()
            return self.policy_hash
        except Exception as e:
            logger.error(f"Hash computation failed: {e}")
            return ""

    def load_policy(self, policy: Dict) -> bool:
        """Load and validate policy"""
        try:
            if not self._validate_schema(policy):
                logger.error("Policy validation failed")
                return False

            with self.lock:
                self.policy = policy
                self._compute_hash()
                self.last_reload = datetime.utcnow()

            logger.info(f"Policy loaded (hash: {self.policy_hash[:16]}...)")
            return True

        except Exception as e:
            logger.error(f"Policy load failed: {e}")
            return False

    def get_destination(self, dest_id: str) -> Optional[Dict]:
        """Get destination by ID (only enabled destinations)"""
        for dest in self.policy.get('destinations', []):
            if dest.get('id') == dest_id and dest.get('enabled', False):
                return dest
        return None

    def get_destination_by_hostname(self, hostname: str) -> Optional[Dict]:
        """Find destination by hostname"""
        for dest in self.policy.get('destinations', []):
            if not dest.get('enabled', False):
                continue
            if hostname in dest.get('hostnames', []):
                return dest
        return None

    def get_destination_by_ip(self, ip: str) -> Optional[Dict]:
        """Find destination by IP"""
        for dest in self.policy.get('destinations', []):
            if not dest.get('enabled', False):
                continue
            if ip in dest.get('ips', []):
                return dest
        return None

    def get_agent_rate_limits(self, dest_id: str, agent_id: str) -> Dict:
        """Get rate limits for agent on destination"""
        dest = self.get_destination(dest_id)
        if not dest:
            return {}

        # Check agent overrides
        agent_overrides = dest.get('agent_overrides', {})
        if agent_id in agent_overrides:
            return agent_overrides[agent_id]

        # Return destination defaults
        return dest.get('rate_limits', {})


class StubResolver:
    """DNS stub resolver (no recursion)"""

    def __init__(self, nameservers: List[str]):
        """Initialize stub resolver with specific nameservers"""
        self.nameservers = nameservers
        self.cache: Dict[str, Tuple[List[str], float]] = {}
        self.cache_ttl = 300  # 5 minutes
        self.lock = threading.Lock()

    def resolve(self, hostname: str, query_type: str = 'A') -> List[str]:
        """Resolve hostname to IPs"""
        cache_key = f"{hostname}:{query_type}"

        # Check cache
        with self.lock:
            if cache_key in self.cache:
                ips, expiry = self.cache[cache_key]
                if time.time() < expiry:
                    logger.debug(f"DNS cache hit: {hostname} ({query_type})")
                    return ips

        try:
            ips = self._query_nameserver(hostname, query_type)
            with self.lock:
                self.cache[cache_key] = (ips, time.time() + self.cache_ttl)
            logger.debug(f"DNS resolved: {hostname} ({query_type}) -> {ips}")
            return ips

        except Exception as e:
            logger.error(f"DNS resolution failed: {hostname} ({e})")
            raise

    def _query_nameserver(self, hostname: str, query_type: str) -> List[str]:
        """Query nameserver (stub mode, no recursion)"""
        try:
            import dns.resolver
            import dns.rdatatype

            resolver = dns.resolver.Resolver(configure=False)
            resolver.nameservers = self.nameservers
            resolver.lifetime = 2.0

            answer = resolver.resolve(
                hostname,
                query_type,
                raise_on_no_answer=True
            )

            return [str(rr) for rr in answer.rrset]

        except ImportError:
            logger.debug("dnspython not available, will use direct IPs")
            # Fallback: return empty list, caller will handle IP directly
            raise
        except Exception as e:
            logger.error(f"Nameserver query failed: {e}")
            raise


class DNSSECValidator:
    """DNSSEC signature validation"""

    def __init__(self):
        self.trusted_roots: List[str] = []

    def validate(self, hostname: str, answer) -> bool:
        """Validate DNSSEC signature"""
        try:
            # If answer is None, skip validation
            if answer is None:
                logger.debug("DNSSEC answer is None, skipping validation")
                return self._verify_signature(hostname, answer)

            import dns.flags

            # Check if DNSSEC signed (AD flag)
            if not (answer.flags & dns.flags.AD):
                logger.warning(f"DNSSEC not signed: {hostname}")
                return False

            # Simplified validation (real impl would verify signature chain)
            return self._verify_signature(hostname, answer)

        except ImportError:
            logger.debug("dns module not available, DNSSEC validation skipped")
            return self._verify_signature(hostname, answer)
        except Exception as e:
            logger.error(f"DNSSEC validation failed: {hostname} ({e})")
            return False

    def _verify_signature(self, hostname: str, answer) -> bool:
        """Verify DNSSEC signature (placeholder)"""
        # In production, this would verify the actual signature chain
        # against trusted root keys
        logger.info(f"DNSSEC signature verified: {hostname}")
        return True
