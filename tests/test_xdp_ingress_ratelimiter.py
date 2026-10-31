# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
tests/test_xdp_ingress_ratelimiter.py — Verification suite for Autonomous eBPF XDP Ingress Rate-Limiter.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model as an in-kernel
eBPF XDP ingress rate-limiting scaffold and autonomous DDoS mitigation prototype.
Zero-Mock Compliance: Real Ed25519 keys, real SQLite-WAL databases, zero mocks.
"""

import time
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.xdp_ingress_ratelimiter import (
    DEFAULT_AGENT_CAPACITY_PACKETS,
    DEFAULT_AGENT_REFILL_RATE_PPS,
    DEFAULT_BASE_QUARANTINE_MS,
    DEFAULT_GLOBAL_CAPACITY_BYTES,
    DEFAULT_GLOBAL_REFILL_BPS,
    DEFAULT_IP_CAPACITY_PACKETS,
    DEFAULT_IP_REFILL_RATE_PPS,
    DEFAULT_VIOLATION_THRESHOLD,
    DEFAULT_VIOLATION_WINDOW_MS,
    HALT_AGENT_RATE_EXCEEDED,
    HALT_AUTH_SIGNATURE_INVALID,
    HALT_ENTITY_QUARANTINED,
    HALT_EPOCH_EXPIRED,
    HALT_GLOBAL_CAPACITY_EXCEEDED,
    HALT_IP_RATE_EXCEEDED,
    HALT_MALFORMED_PACKET,
    MAX_ALLOWED_CLOCK_SKEW_MS,
    MAX_QUARANTINE_LEVEL,
    XDP_ACTION_NAMES,
    XDP_DROP,
    XDP_PASS,
    QuarantineRecord,
    TokenBucket,
    XdpFilterVerdict,
    XdpIngressPacket,
    XdpIngressRateLimiter,
    compute_sha256,
    compute_wilson_ci_bps,
)


def test_01_packet_dataclass_validations() -> None:
    """Verify input validation for XdpIngressPacket."""
    # Valid packet
    pkt = XdpIngressPacket(
        src_ip="192.168.1.100",
        src_port=4433,
        dst_ip="10.0.0.1",
        dst_port=8080,
        protocol="TCP",
        payload_bytes=512,
        timestamp_ms=1729000000000,
    )
    assert pkt.src_ip == "192.168.1.100"
    assert pkt.dst_port == 8080

    # Invalid empty src_ip
    with pytest.raises(ValueError, match="src_ip"):
        XdpIngressPacket(
            src_ip="",
            src_port=4433,
            dst_ip="10.0.0.1",
            dst_port=8080,
            protocol="TCP",
            payload_bytes=512,
            timestamp_ms=1729000000000,
        )

    # Invalid empty dst_ip
    with pytest.raises(ValueError, match="dst_ip"):
        XdpIngressPacket(
            src_ip="192.168.1.100",
            src_port=4433,
            dst_ip="",
            dst_port=8080,
            protocol="TCP",
            payload_bytes=512,
            timestamp_ms=1729000000000,
        )

    # Invalid port bounds
    with pytest.raises(ValueError, match="src_port"):
        XdpIngressPacket(
            src_ip="192.168.1.100",
            src_port=0,
            dst_ip="10.0.0.1",
            dst_port=8080,
            protocol="TCP",
            payload_bytes=512,
            timestamp_ms=1729000000000,
        )

    # Valid dst_port upper boundary: 65535 valid, 65536 invalid (line 147)
    pkt_65535 = XdpIngressPacket(
        src_ip="192.168.1.100",
        src_port=4433,
        dst_ip="10.0.0.1",
        dst_port=65535,
        protocol="TCP",
        payload_bytes=512,
        timestamp_ms=1729000000000,
    )
    assert pkt_65535.dst_port == 65535

    with pytest.raises(ValueError, match="dst_port"):
        XdpIngressPacket(
            src_ip="192.168.1.100",
            src_port=4433,
            dst_ip="10.0.0.1",
            dst_port=65536,
            protocol="TCP",
            payload_bytes=512,
            timestamp_ms=1729000000000,
        )

    with pytest.raises(ValueError, match="dst_port"):
        XdpIngressPacket(
            src_ip="192.168.1.100",
            src_port=4433,
            dst_ip="10.0.0.1",
            dst_port=70000,
            protocol="TCP",
            payload_bytes=512,
            timestamp_ms=1729000000000,
        )

    # Unsupported protocol
    with pytest.raises(ValueError, match="protocol"):
        XdpIngressPacket(
            src_ip="192.168.1.100",
            src_port=4433,
            dst_ip="10.0.0.1",
            dst_port=8080,
            protocol="HTTP",
            payload_bytes=512,
            timestamp_ms=1729000000000,
        )

    # Negative payload
    with pytest.raises(ValueError, match="payload_bytes"):
        XdpIngressPacket(
            src_ip="192.168.1.100",
            src_port=4433,
            dst_ip="10.0.0.1",
            dst_port=8080,
            protocol="TCP",
            payload_bytes=-10,
            timestamp_ms=1729000000000,
        )

    # Non-positive timestamp
    with pytest.raises(ValueError, match="timestamp_ms"):
        XdpIngressPacket(
            src_ip="192.168.1.100",
            src_port=4433,
            dst_ip="10.0.0.1",
            dst_port=8080,
            protocol="TCP",
            payload_bytes=512,
            timestamp_ms=0,
        )


def test_02_packet_caid_and_auth_message() -> None:
    """Verify deterministic RFC 8785 CAID generation and payload sensitivity."""
    pkt1 = XdpIngressPacket(
        src_ip="10.0.0.5",
        src_port=5000,
        dst_ip="10.0.0.1",
        dst_port=80,
        protocol="TCP",
        payload_bytes=100,
        timestamp_ms=1729000000000,
    )
    pkt2 = XdpIngressPacket(
        src_ip="10.0.0.5",
        src_port=5000,
        dst_ip="10.0.0.1",
        dst_port=80,
        protocol="TCP",
        payload_bytes=100,
        timestamp_ms=1729000000000,
    )
    # Identical packets produce identical CAIDs
    caid1 = pkt1.compute_caid()
    caid2 = pkt2.compute_caid()
    assert caid1 == caid2
    assert len(caid1) == 64

    # 1-byte alteration yields distinct CAID
    pkt3 = XdpIngressPacket(
        src_ip="10.0.0.5",
        src_port=5001,
        dst_ip="10.0.0.1",
        dst_port=80,
        protocol="TCP",
        payload_bytes=100,
        timestamp_ms=1729000000000,
    )
    assert pkt3.compute_caid() != caid1

    # Auth message is reproducible
    assert pkt1.compute_auth_message() == pkt2.compute_auth_message()


def test_03_rate_limiter_init_parameters() -> None:
    """Verify rate limiter initialization parameter validations and default configurations."""
    lim_default = XdpIngressRateLimiter()
    assert lim_default.global_refill_bps == DEFAULT_GLOBAL_REFILL_BPS == 10_000_000
    assert lim_default.ip_capacity_packets == DEFAULT_IP_CAPACITY_PACKETS == 100
    assert lim_default.ip_refill_pps == DEFAULT_IP_REFILL_RATE_PPS == 20
    assert lim_default.agent_capacity_packets == DEFAULT_AGENT_CAPACITY_PACKETS == 500
    assert lim_default.agent_refill_pps == DEFAULT_AGENT_REFILL_RATE_PPS == 100
    assert lim_default.violation_threshold == DEFAULT_VIOLATION_THRESHOLD == 5
    assert lim_default.violation_window_ms == DEFAULT_VIOLATION_WINDOW_MS == 10_000
    assert lim_default.base_quarantine_ms == DEFAULT_BASE_QUARANTINE_MS == 15_000
    assert lim_default.max_quarantine_level == MAX_QUARANTINE_LEVEL == 8
    assert lim_default.max_clock_skew_ms == MAX_ALLOWED_CLOCK_SKEW_MS == 60_000

    # Test global_refill_bps == 0 succeeds (line 266 boundary)
    lim_zero_refill = XdpIngressRateLimiter(global_refill_bps=0)
    assert lim_zero_refill.global_refill_bps == 0

    # Test initial global bucket update timestamp (line 290)
    t_now_init = int(time.time() * 1000)
    assert abs(lim_default._global_bucket.last_update_ms - t_now_init) < 1000

    with pytest.raises(ValueError, match="Global capacity"):
        XdpIngressRateLimiter(global_capacity_bytes=0)
    with pytest.raises(ValueError, match="IP capacity"):
        XdpIngressRateLimiter(ip_capacity_packets=0)
    with pytest.raises(ValueError, match="Agent capacity"):
        XdpIngressRateLimiter(agent_capacity_packets=0)
    with pytest.raises(ValueError, match="Violation threshold"):
        XdpIngressRateLimiter(violation_threshold=0)
    with pytest.raises(ValueError, match="Base quarantine"):
        XdpIngressRateLimiter(base_quarantine_ms=0)


def test_04_nominal_packet_admission() -> None:
    """Verify nominal packet ingress passing and token decrement."""
    limiter = XdpIngressRateLimiter(db_path=":memory:", ip_capacity_packets=10, ip_refill_pps=1)
    now_ms = 1729000000000

    pkt = XdpIngressPacket(
        src_ip="192.168.1.50",
        src_port=50000,
        dst_ip="10.0.0.1",
        dst_port=443,
        protocol="TCP",
        payload_bytes=256,
        timestamp_ms=now_ms,
    )

    verdict = limiter.process_packet(pkt, now_ms=now_ms)
    assert verdict.action == XDP_PASS
    assert verdict.verdict_name == "XDP_PASS"
    assert verdict.reason == "ADMITTED"
    assert verdict.tokens_remaining == 9  # 10 capacity - 1 packet consumed
    assert not verdict.quarantined
    assert len(verdict.caid) == 64

    # Second packet from same IP consumes another token
    verdict2 = limiter.process_packet(pkt, now_ms=now_ms)
    assert verdict2.action == XDP_PASS
    assert verdict2.tokens_remaining == 8


def test_05_malformed_ip_packet_drop() -> None:
    """Verify malformed non-IP packets are dropped immediately."""
    limiter = XdpIngressRateLimiter(db_path=":memory:")
    now_ms = 1729000000000

    pkt = XdpIngressPacket(
        src_ip="999.999.999.999",  # Invalid IPv4
        src_port=80,
        dst_ip="10.0.0.1",
        dst_port=443,
        protocol="TCP",
        payload_bytes=100,
        timestamp_ms=now_ms,
    )

    verdict = limiter.process_packet(pkt, now_ms=now_ms)
    assert verdict.action == XDP_DROP
    assert verdict.verdict_name == "XDP_DROP"
    assert verdict.reason == HALT_MALFORMED_PACKET


def test_06_clock_skew_and_epoch_expiration() -> None:
    """Verify packets with excessive clock skew are dropped."""
    limiter = XdpIngressRateLimiter(db_path=":memory:", max_clock_skew_ms=5000)
    now_ms = 1729000000000

    # Stale packet (older than 5000 ms)
    pkt_stale = XdpIngressPacket(
        src_ip="192.168.1.10",
        src_port=80,
        dst_ip="10.0.0.1",
        dst_port=443,
        protocol="TCP",
        payload_bytes=100,
        timestamp_ms=now_ms - 6000,
    )
    verdict_stale = limiter.process_packet(pkt_stale, now_ms=now_ms)
    assert verdict_stale.action == XDP_DROP
    assert verdict_stale.reason == HALT_EPOCH_EXPIRED

    # Future packet (skewed forward by 6000 ms)
    pkt_future = XdpIngressPacket(
        src_ip="192.168.1.10",
        src_port=80,
        dst_ip="10.0.0.1",
        dst_port=443,
        protocol="TCP",
        payload_bytes=100,
        timestamp_ms=now_ms + 6000,
    )
    verdict_future = limiter.process_packet(pkt_future, now_ms=now_ms)
    assert verdict_future.action == XDP_DROP
    assert verdict_future.reason == HALT_EPOCH_EXPIRED


def test_07_per_ip_rate_limiting_exhaustion() -> None:
    """Verify per-IP token bucket exhaustion triggers rate limit drop."""
    limiter = XdpIngressRateLimiter(db_path=":memory:", ip_capacity_packets=3, ip_refill_pps=1)
    now_ms = 1729000000000

    pkt = XdpIngressPacket(
        src_ip="192.168.1.200",
        src_port=1000,
        dst_ip="10.0.0.1",
        dst_port=443,
        protocol="TCP",
        payload_bytes=64,
        timestamp_ms=now_ms,
    )

    # 3 packets pass
    v1 = limiter.process_packet(pkt, now_ms=now_ms)
    v2 = limiter.process_packet(pkt, now_ms=now_ms)
    v3 = limiter.process_packet(pkt, now_ms=now_ms)
    assert v1.action == XDP_PASS
    assert v2.action == XDP_PASS
    assert v3.action == XDP_PASS
    assert v3.tokens_remaining == 0

    # 4th packet dropped
    v4 = limiter.process_packet(pkt, now_ms=now_ms)
    assert v4.action == XDP_DROP
    assert v4.reason == HALT_IP_RATE_EXCEEDED
    assert v4.tokens_remaining == 0


def test_08_progressive_quarantine_escalation() -> None:
    """Verify repetitive rate violations trigger progressive quarantine."""
    limiter = XdpIngressRateLimiter(
        db_path=":memory:",
        ip_capacity_packets=1,
        ip_refill_pps=0,
        violation_threshold=3,
        base_quarantine_ms=5000,
    )
    now_ms = 1729000000000

    pkt = XdpIngressPacket(
        src_ip="192.168.1.99",
        src_port=1000,
        dst_ip="10.0.0.1",
        dst_port=443,
        protocol="UDP",
        payload_bytes=64,
        timestamp_ms=now_ms,
    )

    # Consume single token
    v0 = limiter.process_packet(pkt, now_ms=now_ms)
    assert v0.action == XDP_PASS

    # Violation 1
    v1 = limiter.process_packet(pkt, now_ms=now_ms)
    assert v1.action == XDP_DROP
    assert not v1.quarantined

    # Violation 2
    v2 = limiter.process_packet(pkt, now_ms=now_ms)
    assert v2.action == XDP_DROP
    assert not v2.quarantined

    # Violation 3 -> Escalates to quarantine (Level 1)
    v3 = limiter.process_packet(pkt, now_ms=now_ms)
    assert v3.action == XDP_DROP
    assert v3.quarantined

    # Subsequent packet immediately dropped under quarantine
    v4 = limiter.process_packet(pkt, now_ms=now_ms + 100)
    assert v4.action == XDP_DROP
    assert v4.reason == HALT_ENTITY_QUARANTINED
    assert v4.quarantined

    # Check active quarantines list
    active = limiter.list_active_quarantines(now_ms=now_ms + 100)
    assert len(active) == 1
    assert active[0]["entity_key"] == "192.168.1.99"
    assert active[0]["level"] == 1
    assert active[0]["remaining_ms"] == 4900


def test_09_quarantine_expiry_and_auto_release() -> None:
    """Verify quarantine expires and entity is released after quarantine duration."""
    limiter = XdpIngressRateLimiter(
        db_path=":memory:",
        ip_capacity_packets=5,
        ip_refill_pps=5,
        violation_threshold=2,
        base_quarantine_ms=4000,
    )
    now_ms = 1729000000000

    pkt = XdpIngressPacket(
        src_ip="192.168.1.88",
        src_port=1000,
        dst_ip="10.0.0.1",
        dst_port=443,
        protocol="TCP",
        payload_bytes=64,
        timestamp_ms=now_ms,
    )

    # Exhaust capacity
    for _ in range(5):
        limiter.process_packet(pkt, now_ms=now_ms)

    # Violations
    limiter.process_packet(pkt, now_ms=now_ms)  # 1
    v_quar = limiter.process_packet(pkt, now_ms=now_ms)  # 2 -> Quarantined
    assert v_quar.quarantined

    # During quarantine: blocked
    v_blocked = limiter.process_packet(pkt, now_ms=now_ms + 2000)
    assert v_blocked.action == XDP_DROP
    assert v_blocked.reason == HALT_ENTITY_QUARANTINED

    # Advance time past 4000ms: quarantine expires
    # Also tokens have replenished (4000ms * 5 pps / 1000 = 20 tokens -> capped at 5)
    v_released = limiter.process_packet(pkt, now_ms=now_ms + 4001)
    assert v_released.action == XDP_PASS
    assert not v_released.quarantined

    # Quarantine list is now empty
    active = limiter.list_active_quarantines(now_ms=now_ms + 4001)
    assert len(active) == 0


def test_10_authenticated_agent_packet_handling() -> None:
    """Verify Ed25519 authenticated sovereign agent communication."""
    limiter = XdpIngressRateLimiter(
        db_path=":memory:",
        agent_capacity_packets=50,
        agent_refill_pps=10,
    )
    now_ms = 1729000000000

    # Generate Ed25519 keypair
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    pubkey_hex = public_key.public_bytes_raw().hex()

    # Create un-signed template
    agent_id = "agent:sov:aeib:node-01"
    tmp_pkt = XdpIngressPacket(
        src_ip="172.16.0.10",
        src_port=9000,
        dst_ip="10.0.0.1",
        dst_port=443,
        protocol="TCP",
        payload_bytes=128,
        timestamp_ms=now_ms,
        agent_id=agent_id,
        auth_pubkey_hex=pubkey_hex,
    )
    msg = tmp_pkt.compute_auth_message()
    sig_hex = private_key.sign(msg).hex()

    # Legitimate signed packet
    valid_pkt = XdpIngressPacket(
        src_ip="172.16.0.10",
        src_port=9000,
        dst_ip="10.0.0.1",
        dst_port=443,
        protocol="TCP",
        payload_bytes=128,
        timestamp_ms=now_ms,
        agent_id=agent_id,
        auth_signature_hex=sig_hex,
        auth_pubkey_hex=pubkey_hex,
    )
    verdict = limiter.process_packet(valid_pkt, now_ms=now_ms)
    assert verdict.action == XDP_PASS
    assert verdict.reason == "ADMITTED"
    assert verdict.tokens_remaining == 49

    # Tampered signature
    tampered_sig_hex = ("00" * 32) + sig_hex[64:]
    tampered_pkt = XdpIngressPacket(
        src_ip="172.16.0.10",
        src_port=9000,
        dst_ip="10.0.0.1",
        dst_port=443,
        protocol="TCP",
        payload_bytes=128,
        timestamp_ms=now_ms,
        agent_id=agent_id,
        auth_signature_hex=tampered_sig_hex,
        auth_pubkey_hex=pubkey_hex,
    )
    bad_verdict = limiter.process_packet(tampered_pkt, now_ms=now_ms)
    assert bad_verdict.action == XDP_DROP
    assert bad_verdict.reason == HALT_AUTH_SIGNATURE_INVALID


def test_11_global_bandwidth_capacity_exhaustion() -> None:
    """Verify global bandwidth capacity cap drops oversized bursts."""
    limiter = XdpIngressRateLimiter(
        db_path=":memory:",
        global_capacity_bytes=1000,
        global_refill_bps=100,
    )
    now_ms = 1729000000000

    pkt = XdpIngressPacket(
        src_ip="192.168.1.15",
        src_port=4000,
        dst_ip="10.0.0.1",
        dst_port=443,
        protocol="TCP",
        payload_bytes=600,
        timestamp_ms=now_ms,
    )

    # First packet: 600 bytes consumed from 1000 -> 400 remaining
    v1 = limiter.process_packet(pkt, now_ms=now_ms)
    assert v1.action == XDP_PASS

    # Second packet: 600 bytes requested, only 400 available -> dropped
    v2 = limiter.process_packet(pkt, now_ms=now_ms)
    assert v2.action == XDP_DROP
    assert v2.reason == HALT_GLOBAL_CAPACITY_EXCEEDED


def test_12_token_replenishment_over_time() -> None:
    """Verify leaky token bucket replenishment mathematics."""
    bucket = TokenBucket(
        capacity=100,
        refill_rate_per_sec=50,
        current_tokens=0,
        last_update_ms=1000,
    )

    # In-past time: no change
    bucket.replenish(500)
    assert bucket.current_tokens == 0

    # 1 second later: 50 tokens added
    bucket.replenish(2000)
    assert bucket.current_tokens == 50

    # 2 seconds later: another 100 tokens, capped at capacity 100
    bucket.replenish(4000)
    assert bucket.current_tokens == 100


def test_13_sqlite_persistence_queries_and_summary() -> None:
    """Verify SQLite-WAL query helpers and traffic summary aggregation."""
    limiter = XdpIngressRateLimiter(db_path=":memory:")
    now_ms = 1729000000000

    pkt_pass = XdpIngressPacket(
        src_ip="10.1.1.1",
        src_port=5000,
        dst_ip="10.0.0.1",
        dst_port=443,
        protocol="TCP",
        payload_bytes=100,
        timestamp_ms=now_ms,
    )
    v_pass = limiter.process_packet(pkt_pass, now_ms=now_ms)

    # Query verdict by CAID
    record = limiter.get_verdict_by_caid(v_pass.caid)
    assert record is not None
    assert record["caid"] == v_pass.caid
    assert record["action"] == XDP_PASS
    assert record["src_ip"] == "10.1.1.1"

    # Non-existent CAID
    assert limiter.get_verdict_by_caid("00" * 32) is None

    # Traffic summary
    summary = limiter.get_traffic_summary()
    assert summary["total_packets"] == 1
    assert summary["counts_by_action"]["XDP_PASS"] == 1
    assert summary["pass_ratio_bps"] == 10000


def test_14_exact_mutation_boundaries() -> None:
    """Exercise boundary conditions and edge cases to kill mutation survivors."""
    # 0. Assert all default constants
    assert DEFAULT_GLOBAL_CAPACITY_BYTES == 50_000_000
    assert DEFAULT_GLOBAL_REFILL_BPS == 10_000_000
    assert DEFAULT_IP_CAPACITY_PACKETS == 100
    assert DEFAULT_IP_REFILL_RATE_PPS == 20
    assert DEFAULT_AGENT_CAPACITY_PACKETS == 500
    assert DEFAULT_AGENT_REFILL_RATE_PPS == 100
    assert DEFAULT_VIOLATION_THRESHOLD == 5
    assert DEFAULT_VIOLATION_WINDOW_MS == 10_000
    assert DEFAULT_BASE_QUARANTINE_MS == 15_000
    assert MAX_QUARANTINE_LEVEL == 8
    assert MAX_ALLOWED_CLOCK_SKEW_MS == 60_000

    # 1. TokenBucket consume failure returns False
    tb = TokenBucket(capacity=10, refill_rate_per_sec=1, current_tokens=2, last_update_ms=1000)
    assert tb.consume(5, 1000) is False
    assert tb.consume(2, 1000) is True

    # 2. XdpFilterVerdict validation
    with pytest.raises(ValueError, match="packet_caid must be non-empty"):
        XdpFilterVerdict(
            action=XDP_PASS,
            verdict_name="XDP_PASS",
            reason="TEST",
            src_ip="1.1.1.1",
            packet_caid="",
            tokens_remaining=0,
            quarantined=False,
            timestamp_ms=1000,
            caid="abcd",
        )
    with pytest.raises(ValueError, match="caid must be non-empty"):
        XdpFilterVerdict(
            action=XDP_PASS,
            verdict_name="XDP_PASS",
            reason="TEST",
            src_ip="1.1.1.1",
            packet_caid="abcd",
            tokens_remaining=0,
            quarantined=False,
            timestamp_ms=1000,
            caid="",
        )

    # 3. Port boundaries: exactly 65535 passes, 65536 fails, 1 passes, 0 fails
    p_max = XdpIngressPacket(
        src_ip="1.1.1.1",
        src_port=65535,
        dst_ip="2.2.2.2",
        dst_port=65535,
        protocol="TCP",
        payload_bytes=10,
        timestamp_ms=1000,
    )
    assert p_max.src_port == 65535
    with pytest.raises(ValueError, match="src_port"):
        XdpIngressPacket(
            src_ip="1.1.1.1",
            src_port=65536,
            dst_ip="2.2.2.2",
            dst_port=80,
            protocol="TCP",
            payload_bytes=10,
            timestamp_ms=1000,
        )
    with pytest.raises(ValueError, match="dst_port"):
        XdpIngressPacket(
            src_ip="1.1.1.1",
            src_port=80,
            dst_ip="2.2.2.2",
            dst_port=65536,
            protocol="TCP",
            payload_bytes=10,
            timestamp_ms=1000,
        )

    # 4. Negative and zero init validation branches
    # zero refill rates are allowed
    lim_zero = XdpIngressRateLimiter(global_refill_bps=0, ip_refill_pps=0, agent_refill_pps=0)
    assert lim_zero.global_refill_bps == 0
    assert lim_zero.ip_refill_pps == 0
    assert lim_zero.agent_refill_pps == 0

    # Exactly 1 capacity is allowed; 0 is rejected (kills line 266 constant 0 perturbation)
    lim_1b = XdpIngressRateLimiter(global_capacity_bytes=1, ip_capacity_packets=1, agent_capacity_packets=1)
    assert lim_1b.global_capacity_bytes == 1
    assert lim_1b.ip_capacity_packets == 1
    assert lim_1b.agent_capacity_packets == 1
    with pytest.raises(ValueError, match="Global capacity"):
        XdpIngressRateLimiter(global_capacity_bytes=0)
    with pytest.raises(ValueError, match="IP capacity"):
        XdpIngressRateLimiter(ip_capacity_packets=0)
    with pytest.raises(ValueError, match="Agent capacity"):
        XdpIngressRateLimiter(agent_capacity_packets=0)

    # negative values raise ValueError
    with pytest.raises(ValueError, match="Global capacity"):
        XdpIngressRateLimiter(global_refill_bps=-1)
    with pytest.raises(ValueError, match="IP capacity"):
        XdpIngressRateLimiter(ip_refill_pps=-1)
    with pytest.raises(ValueError, match="Agent capacity"):
        XdpIngressRateLimiter(agent_refill_pps=-1)
    with pytest.raises(ValueError, match="Violation threshold"):
        XdpIngressRateLimiter(violation_window_ms=-1)
    with pytest.raises(ValueError, match="Base quarantine"):
        XdpIngressRateLimiter(base_quarantine_ms=-1)

    # Check that initial bucket timestamp is close to current time
    t_start = int(time.time() * 1000)
    lim_time = XdpIngressRateLimiter(db_path=":memory:")
    assert abs(lim_time._global_bucket.last_update_ms - t_start) <= 5000

    # 5. _verify_agent_signature malformed pubkey and sig lengths
    limiter = XdpIngressRateLimiter(
        db_path=":memory:",
        ip_capacity_packets=2,
        ip_refill_pps=1,
        violation_threshold=1,
        max_quarantine_level=2,
        base_quarantine_ms=1000,
    )
    now_ms = 1729000000000

    # missing sig
    p_no_sig = XdpIngressPacket(
        src_ip="1.1.1.1",
        src_port=80,
        dst_ip="2.2.2.2",
        dst_port=80,
        protocol="TCP",
        payload_bytes=10,
        timestamp_ms=now_ms,
        agent_id="agent:1",
        auth_pubkey_hex="00" * 32,
        auth_signature_hex=None,
    )
    assert limiter._verify_agent_signature(p_no_sig) is False

    # missing pubkey
    p_no_pk = XdpIngressPacket(
        src_ip="1.1.1.1",
        src_port=80,
        dst_ip="2.2.2.2",
        dst_port=80,
        protocol="TCP",
        payload_bytes=10,
        timestamp_ms=now_ms,
        agent_id="agent:1",
        auth_pubkey_hex=None,
        auth_signature_hex="00" * 64,
    )
    assert limiter._verify_agent_signature(p_no_pk) is False

    # invalid lengths (16 bytes pubkey, 32 bytes sig)
    p_short = XdpIngressPacket(
        src_ip="1.1.1.1",
        src_port=80,
        dst_ip="2.2.2.2",
        dst_port=80,
        protocol="TCP",
        payload_bytes=10,
        timestamp_ms=now_ms,
        agent_id="agent:1",
        auth_pubkey_hex="00" * 16,
        auth_signature_hex="00" * 32,
    )
    assert limiter._verify_agent_signature(p_short) is False

    # invalid hex
    p_bad_hex = XdpIngressPacket(
        src_ip="1.1.1.1",
        src_port=80,
        dst_ip="2.2.2.2",
        dst_port=80,
        protocol="TCP",
        payload_bytes=10,
        timestamp_ms=now_ms,
        agent_id="agent:1",
        auth_pubkey_hex="zz" * 32,
        auth_signature_hex="zz" * 64,
    )
    assert limiter._verify_agent_signature(p_bad_hex) is False

    # 6. Default now_ms execution path (time.time() fallback)
    pkt_default = XdpIngressPacket(
        src_ip="10.2.2.2",
        src_port=1234,
        dst_ip="10.0.0.1",
        dst_port=80,
        protocol="TCP",
        payload_bytes=64,
        timestamp_ms=int(time.time() * 1000),
    )
    v_default = limiter.process_packet(pkt_default)
    assert v_default.action == XDP_PASS

    # 7. Max quarantine level ceiling
    pkt_quar = XdpIngressPacket(
        src_ip="10.3.3.3",
        src_port=1234,
        dst_ip="10.0.0.1",
        dst_port=80,
        protocol="TCP",
        payload_bytes=64,
        timestamp_ms=now_ms,
    )
    # Drain tokens
    limiter.process_packet(pkt_quar, now_ms=now_ms)
    limiter.process_packet(pkt_quar, now_ms=now_ms)

    # Violate repeatedly to hit max_quarantine_level
    limiter.process_packet(pkt_quar, now_ms=now_ms)
    limiter.process_packet(pkt_quar, now_ms=now_ms + 10)
    limiter.process_packet(pkt_quar, now_ms=now_ms + 20)

    quars = limiter.list_active_quarantines(now_ms=now_ms + 25)
    assert len(quars) == 1
    assert quars[0]["level"] <= 2
    assert quars[0]["last_violation_ms"] == now_ms
    assert quars[0]["violation_count"] >= 1
    assert quars[0]["reason"] == HALT_IP_RATE_EXCEEDED

    # Test list_active_quarantines default now_ms parameter with live quarantine
    live_limiter = XdpIngressRateLimiter(
        db_path=":memory:",
        ip_capacity_packets=1,
        ip_refill_pps=0,
        violation_threshold=1,
        base_quarantine_ms=60000,
    )
    t_live = int(time.time() * 1000)
    p_live = XdpIngressPacket(
        src_ip="192.168.10.10",
        src_port=80,
        dst_ip="10.0.0.1",
        dst_port=80,
        protocol="TCP",
        payload_bytes=10,
        timestamp_ms=t_live,
    )
    live_limiter.process_packet(p_live, now_ms=t_live)
    live_limiter.process_packet(p_live, now_ms=t_live)  # triggers quarantine
    active_live = live_limiter.list_active_quarantines()
    assert len(active_live) == 1
    assert 50000 <= active_live[0]["remaining_ms"] <= 61000
    assert active_live[0]["last_violation_ms"] == t_live

    # 8. Empty traffic summary
    lim_empty = XdpIngressRateLimiter(db_path=":memory:")
    summary_empty = lim_empty.get_traffic_summary()
    assert summary_empty["total_packets"] == 0
    assert summary_empty["pass_ratio_bps"] == 0
    assert summary_empty["counts_by_action"]["XDP_PASS"] == 0
    assert summary_empty["counts_by_action"]["XDP_DROP"] == 0
    assert summary_empty["counts_by_action"]["XDP_TX"] == 0
    assert summary_empty["counts_by_action"]["XDP_REDIRECT"] == 0
    assert summary_empty["counts_by_action"]["XDP_ABORTED"] == 0

    # 9. Invalid verdict action in dataclass
    with pytest.raises(ValueError, match="Invalid XDP action"):
        XdpFilterVerdict(
            action=99,
            verdict_name="UNKNOWN",
            reason="TEST",
            src_ip="1.1.1.1",
            packet_caid="abcd",
            tokens_remaining=0,
            quarantined=False,
            timestamp_ms=1000,
            caid="ef01",
        )

    # 10. Empty caid validation in XdpFilterVerdict (line 203)
    with pytest.raises(ValueError, match="caid must be non-empty"):
        XdpFilterVerdict(
            action=XDP_PASS,
            verdict_name="XDP_PASS",
            reason="TEST",
            src_ip="1.1.1.1",
            packet_caid="abcd",
            tokens_remaining=0,
            quarantined=False,
            timestamp_ms=1000,
            caid="",
        )

    # 11. TokenBucket.consume returning strictly False on exhausted bucket (line 230)
    tb = TokenBucket(capacity=10, refill_rate_per_sec=0, current_tokens=5, last_update_ms=1000)
    assert tb.consume(10, 1000) is False

    # 12. _verify_agent_signature asymmetric None inputs (line 418 bool swap)
    lim_sig = XdpIngressRateLimiter()
    pkt_only_pub = XdpIngressPacket(
        src_ip="1.1.1.1", src_port=80, dst_ip="2.2.2.2", dst_port=80, protocol="TCP",
        payload_bytes=10, timestamp_ms=1000, auth_pubkey_hex="aa" * 32, auth_signature_hex=None,
    )
    assert lim_sig._verify_agent_signature(pkt_only_pub) is False

    pkt_only_sig = XdpIngressPacket(
        src_ip="1.1.1.1", src_port=80, dst_ip="2.2.2.2", dst_port=80, protocol="TCP",
        payload_bytes=10, timestamp_ms=1000, auth_pubkey_hex=None, auth_signature_hex="bb" * 64,
    )
    assert lim_sig._verify_agent_signature(pkt_only_sig) is False

    # 13. list_active_quarantines() with expired quarantine and default now_ms (line 662 Mult swap)
    lim_exp = XdpIngressRateLimiter()
    with lim_exp._conn:
        lim_exp._conn.execute(
            """
            INSERT INTO xdp_quarantine_ledger (
                entity_key, level, quarantine_until_ms, violation_count, last_violation_ms, reason
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("192.168.99.99", 1, int(time.time() * 1000) - 10000, 1, int(time.time() * 1000) - 20000, "EXPIRED"),
        )
    assert len(lim_exp.list_active_quarantines()) == 0

    # 14. list_active_quarantines() row attribute type verification (line 682 row[4] int vs row[5] str)
    with lim_exp._conn:
        lim_exp._conn.execute(
            """
            INSERT INTO xdp_quarantine_ledger (
                entity_key, level, quarantine_until_ms, violation_count, last_violation_ms, reason
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("192.168.99.98", 2, int(time.time() * 1000) + 50000, 3, 1729000000000, "TYPE_CHECK"),
        )
    quar_rows = lim_exp.list_active_quarantines()
    assert len(quar_rows) == 1
    assert isinstance(quar_rows[0]["last_violation_ms"], int)
    assert quar_rows[0]["last_violation_ms"] == 1729000000000
    assert isinstance(quar_rows[0]["reason"], str)
    assert quar_rows[0]["reason"] == "TYPE_CHECK"


def test_16_agent_rate_limiting_and_quarantine() -> None:
    """Verify per-agent rate limit exhaustion and agent quarantine across IPs."""
    limiter = XdpIngressRateLimiter(
        db_path=":memory:",
        agent_capacity_packets=1,
        agent_refill_pps=0,
        violation_threshold=1,
        base_quarantine_ms=10000,
    )
    now_ms = 1729000000000

    private_key = ed25519.Ed25519PrivateKey.generate()
    pubkey_hex = private_key.public_key().public_bytes_raw().hex()
    agent_id = "agent:sov:aeib:node-quarantine"

    def make_signed_pkt(src_ip: str) -> XdpIngressPacket:
        pkt = XdpIngressPacket(
            src_ip=src_ip,
            src_port=9000,
            dst_ip="10.0.0.1",
            dst_port=443,
            protocol="TCP",
            payload_bytes=128,
            timestamp_ms=now_ms,
            agent_id=agent_id,
            auth_pubkey_hex=pubkey_hex,
        )
        sig_hex = private_key.sign(pkt.compute_auth_message()).hex()
        return XdpIngressPacket(
            src_ip=src_ip,
            src_port=9000,
            dst_ip="10.0.0.1",
            dst_port=443,
            protocol="TCP",
            payload_bytes=128,
            timestamp_ms=now_ms,
            agent_id=agent_id,
            auth_signature_hex=sig_hex,
            auth_pubkey_hex=pubkey_hex,
        )

    # First packet passes
    pkt1 = make_signed_pkt("172.16.0.1")
    v1 = limiter.process_packet(pkt1, now_ms=now_ms)
    assert v1.action == XDP_PASS

    # Second packet exceeds agent rate limit -> triggers quarantine (threshold=1)
    pkt2 = make_signed_pkt("172.16.0.1")
    v2 = limiter.process_packet(pkt2, now_ms=now_ms)
    assert v2.action == XDP_DROP
    assert v2.reason == HALT_AGENT_RATE_EXCEEDED
    assert v2.quarantined is True

    # Third packet from a completely different IP but same agent_id is blocked under quarantine
    pkt3 = make_signed_pkt("172.16.0.2")
    v3 = limiter.process_packet(pkt3, now_ms=now_ms + 10)
    assert v3.action == XDP_DROP
    assert v3.reason == HALT_ENTITY_QUARANTINED
    assert v3.quarantined is True


def test_15_wilson_ci_bounds_and_epistemic_lexicon() -> None:
    """Verify conservative Wilson 95% confidence interval and epistemic integrity."""
    # Wilson CI tests
    low, high = compute_wilson_ci_bps(27, 30)
    assert low == 7438
    assert high == 9654

    low_zero, high_zero = compute_wilson_ci_bps(0, 0)
    assert low_zero == 0 and high_zero == 0

    low_invalid, high_invalid = compute_wilson_ci_bps(-1, 10)
    assert low_invalid == 0 and high_invalid == 0

    # Epistemic docstring scan for required status and scaffold terms
    import src.xdp_ingress_ratelimiter as mod
    doc = mod.__doc__ or ""
    assert "INTERNAL PREVIEW COMMISSIONED" in doc
    assert "scaffold" in doc.lower() or "simulated" in doc.lower()
