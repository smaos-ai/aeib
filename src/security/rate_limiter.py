"""
L5B: Rate Limiting & Quota Tracking
Sliding window rate limiter and per-agent quota enforcement
"""

import time
import threading
from collections import defaultdict, deque
from typing import Dict, Deque
import logging

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """Sliding window rate limiter (per destination, per agent)"""

    def __init__(self):
        """Initialize rate limiter"""
        # buckets[dest_id][agent_id] = deque of request timestamps
        self.buckets: Dict[str, Dict[str, Deque[float]]] = defaultdict(
            lambda: defaultdict(deque)
        )
        self.lock = threading.Lock()

    def is_allowed(
        self,
        dest_id: str,
        agent_id: str,
        rate_limit: int,
        window_sec: int = 1
    ) -> bool:
        """
        Check if request is allowed under rate limit.

        Args:
            dest_id: Destination ID
            agent_id: Agent ID
            rate_limit: Max requests per window_sec
            window_sec: Time window in seconds

        Returns:
            True if allowed, False if denied
        """
        now = time.time()
        window_start = now - window_sec

        with self.lock:
            bucket = self.buckets[dest_id][agent_id]

            # Remove expired entries
            while bucket and bucket[0] < window_start:
                bucket.popleft()

            # Check limit
            if len(bucket) >= rate_limit:
                logger.warning(
                    f"Rate limit exceeded: {dest_id}/{agent_id} "
                    f"({len(bucket)} >= {rate_limit})"
                )
                return False

            # Add timestamp
            bucket.append(now)
            return True

    def reset(self, dest_id: str = None, agent_id: str = None) -> None:
        """Reset rate limiter state"""
        with self.lock:
            if dest_id and agent_id:
                if dest_id in self.buckets and agent_id in self.buckets[dest_id]:
                    del self.buckets[dest_id][agent_id]
            elif dest_id:
                if dest_id in self.buckets:
                    del self.buckets[dest_id]
            else:
                self.buckets.clear()


class PerAgentQuotaTracker:
    """Per-agent quota tracking (bytes/sec)"""

    def __init__(self):
        """Initialize quota tracker"""
        # quotas[agent_id] = {'bytes': 0, 'reset_at': timestamp}
        self.quotas: Dict[str, Dict] = defaultdict(
            lambda: {'bytes': 0, 'reset_at': time.time() + 1}
        )
        self.lock = threading.Lock()

    def consume(
        self,
        agent_id: str,
        bytes_sent: int,
        bytes_per_sec_limit: int
    ) -> bool:
        """
        Consume quota. Returns False if limit exceeded.

        Args:
            agent_id: Agent ID
            bytes_sent: Bytes sent in this request
            bytes_per_sec_limit: Bytes per second limit

        Returns:
            True if allowed, False if quota exceeded
        """
        now = time.time()

        with self.lock:
            quota = self.quotas[agent_id]

            # Reset window if expired
            if now > quota['reset_at']:
                quota['bytes'] = 0
                quota['reset_at'] = now + 1

            # Check limit
            if quota['bytes'] + bytes_sent > bytes_per_sec_limit:
                logger.warning(
                    f"Quota exceeded: {agent_id} "
                    f"({quota['bytes'] + bytes_sent} > {bytes_per_sec_limit})"
                )
                return False

            quota['bytes'] += bytes_sent
            return True

    def reset(self, agent_id: str = None) -> None:
        """Reset quota tracker state"""
        with self.lock:
            if agent_id:
                if agent_id in self.quotas:
                    del self.quotas[agent_id]
            else:
                self.quotas.clear()

    def get_usage(self, agent_id: str) -> Dict:
        """Get quota usage for agent"""
        with self.lock:
            if agent_id in self.quotas:
                quota = self.quotas[agent_id].copy()
                return quota
            return {'bytes': 0, 'reset_at': time.time() + 1}
