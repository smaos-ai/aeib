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
tests/test_tetragon_ebpf_stream_parser.py
================================================================================
Cleanroom verification test suite for Tetragon eBPF Stream Ingestion Engine.
Zero mocks, deterministic assertions, full branch and edge-case coverage.
"""

from dataclasses import FrozenInstanceError
import json
import pytest

from src.tetragon_ebpf_stream_parser import (
    DEFAULT_ALLOWED_GATEWAY_PORTS,
    TetragonAuditReceipt,
    TetragonEBPFStreamParser,
    TetragonEvent,
)

SAMPLE_SPIFFE_ID = "spiffe://smaos.internal/ns/production/sa/aeib-worker/actor/001"
SAMPLE_DIGEST = "sha256:11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff"


def test_init_validation() -> None:
    # Valid initialization with defaults
    parser = TetragonEBPFStreamParser(
        actor_spiffe_id=SAMPLE_SPIFFE_ID,
        bpf_lsm_profile_digest=SAMPLE_DIGEST,
    )
    assert parser.actor_spiffe_id == SAMPLE_SPIFFE_ID
    assert parser.bpf_lsm_profile_digest == SAMPLE_DIGEST
    assert parser.allowed_gateway_ports == frozenset({15001})  # claim: config
    assert 15001 in DEFAULT_ALLOWED_GATEWAY_PORTS  # claim: config

    # Invalid SPIFFE
    with pytest.raises(ValueError, match="ERR_INVALID_SPIFFE_ID"):
        TetragonEBPFStreamParser(
            actor_spiffe_id="invalid-id",
            bpf_lsm_profile_digest=SAMPLE_DIGEST,
        )

    # Invalid profile digest
    with pytest.raises(ValueError, match="ERR_INVALID_BPF_PROFILE_DIGEST"):
        TetragonEBPFStreamParser(
            actor_spiffe_id=SAMPLE_SPIFFE_ID,
            bpf_lsm_profile_digest="md5:bad",
        )


def test_dataclass_frozen_immutability() -> None:
    event = TetragonEvent(
        event_type="PROCESS_EXEC",
        function_name="sys_enter_execve",
        action="EXEC_ACTION_POST",
        pod_namespace="production",
        pod_name="worker-pod",
        container_name="worker",
        pid=123,
        binary="/bin/ls",
        arguments="",
        details={},
        timestamp="2026-10-31T02:00:00Z",
    )
    with pytest.raises(FrozenInstanceError):
        event.pid = 999  # type: ignore

    receipt = TetragonAuditReceipt(
        stream_id="stream-1",
        actor_spiffe_id=SAMPLE_SPIFFE_ID,
        bpf_lsm_profile_digest=SAMPLE_DIGEST,
        total_events_evaluated=0,
        allowed_events_count=0,
        blocked_events_count=0,
        policy_violations=(),
        integrity_score_bps=10000,
        receipt_caid="sha256:1234",
    )
    with pytest.raises(FrozenInstanceError):
        receipt.integrity_score_bps = 5000  # type: ignore


def test_parse_raw_event_formats_and_types() -> None:
    parser = TetragonEBPFStreamParser(SAMPLE_SPIFFE_ID, SAMPLE_DIGEST)

    # 1. Process Exec JSON string
    exec_json = json.dumps(
        {
            "process_exec": {
                "process": {
                    "pid": 1042,
                    "binary": "/usr/bin/python3",
                    "arguments": "worker.py",
                    "cwd": "/app",
                    "pod": {
                        "namespace": "production",
                        "name": "worker-pod-xyz",
                        "container": {"name": "worker"},
                    },
                },
                "parent": {"pid": 1},
            },
            "time": "2026-10-31T02:00:00Z",
        }
    )
    event_exec = parser.parse_raw_event(exec_json)
    assert event_exec.event_type == "PROCESS_EXEC"
    assert event_exec.function_name == "sys_enter_execve"
    assert event_exec.pid == 1042
    assert event_exec.binary == "/usr/bin/python3"
    assert event_exec.pod_namespace == "production"
    assert event_exec.pod_name == "worker-pod-xyz"
    assert event_exec.container_name == "worker"
    assert event_exec.timestamp == "2026-10-31T02:00:00Z"

    # Dict representation
    event_dict = event_exec.to_dict()
    assert event_dict["event_type"] == "PROCESS_EXEC"
    assert event_dict["pid"] == 1042

    # 2. Process Kprobe dict with missing PID (defaults to 0)
    kprobe_dict = {
        "process_kprobe": {
            "process": {"binary": "/bin/curl"},
            "function_name": "sys_enter_connect",
            "action": "KPROBE_ACTION_POST",
            "args": [
                {
                    "sock_arg": {
                        "daddr": "127.0.0.1",
                        "dport": 15001,
                    }
                }
            ],
        },
        "time": "2026-10-31T02:01:00Z",
    }
    event_kprobe = parser.parse_raw_event(kprobe_dict)
    assert event_kprobe.event_type == "PROCESS_KPROBE"
    assert event_kprobe.function_name == "sys_enter_connect"
    assert event_kprobe.pid == 0

    # 3. Process LSM dict
    lsm_dict = {
        "process_lsm": {
            "process": {"pid": 3099, "binary": "/bin/cat"},
            "function_name": "security_file_open",
            "action": "LSM_ACTION_SIGKILL",
            "args": [{"file_arg": {"path": "/etc/shadow"}}],
        },
        "time": "2026-10-31T02:02:00Z",
    }
    event_lsm = parser.parse_raw_event(lsm_dict)
    assert event_lsm.event_type == "PROCESS_LSM"
    assert event_lsm.action == "LSM_ACTION_SIGKILL"

    # 4. Unknown event structure
    unknown_dict = {
        "process": {"pid": 4001, "binary": "/bin/test"},
        "function_name": "custom_call",
        "action": "CUSTOM_ACTION",
    }
    event_unknown = parser.parse_raw_event(unknown_dict)
    assert event_unknown.event_type == "UNKNOWN"
    assert event_unknown.function_name == "custom_call"

    # 5. Malformed JSON
    with pytest.raises(ValueError, match="ERR_MALFORMED_JSON"):
        parser.parse_raw_event("{broken:json")

    # 6. Unsupported input type
    with pytest.raises(ValueError, match="ERR_UNSUPPORTED_TYPE"):
        parser.parse_raw_event(12345)  # type: ignore


def test_evaluate_allowed_and_blocked_network_egress() -> None:
    parser = TetragonEBPFStreamParser(SAMPLE_SPIFFE_ID, SAMPLE_DIGEST)

    # Allowed: connection to localhost port 15001 (agentgateway egress proxy)
    allowed_connect = {
        "process_kprobe": {
            "process": {"pid": 100},
            "function_name": "sys_enter_connect",
            "args": [{"sock_arg": {"daddr": "127.0.0.1", "dport": 15001}}],
        }
    }
    ev_allowed = parser.parse_raw_event(allowed_connect)
    is_allowed, reason = parser.evaluate_event(ev_allowed)
    assert is_allowed is True
    assert reason is None

    # Allowed: connection to arbitrary external destination IP via allowed port 15001
    # When dport == 15001, connection routes to local sidecar proxy, regardless of destination IP
    allowed_proxy_routed = {
        "process_kprobe": {
            "process": {"pid": 100},
            "function_name": "sys_enter_connect",
            "args": [{"sock_arg": {"daddr": "198.51.100.99", "dport": 15001}}],
        }
    }
    ev_proxy_routed = parser.parse_raw_event(allowed_proxy_routed)
    is_allowed_proxy, reason_proxy = parser.evaluate_event(ev_proxy_routed)
    assert is_allowed_proxy is True
    assert reason_proxy is None

    # Allowed: connection to configured gateway cluster IP
    allowed_cluster_ip = {
        "process_kprobe": {
            "process": {"pid": 100},
            "function_name": "sys_enter_connect",
            "args": [{"sock_arg": {"daddr": "10.96.0.10", "dport": 443}}],
        }
    }
    ev_cluster = parser.parse_raw_event(allowed_cluster_ip)
    is_allowed_cluster, _ = parser.evaluate_event(ev_cluster)
    assert is_allowed_cluster is True

    # Blocked: direct outbound connect to external IP bypassing gateway (port 443 != 15001)
    blocked_connect = {
        "process_kprobe": {
            "process": {"pid": 101, "binary": "/usr/bin/curl"},
            "function_name": "sys_enter_connect",
            "args": [{"sock_arg": {"daddr": "198.51.100.1", "dport": 443}}],
        }
    }
    ev_blocked = parser.parse_raw_event(blocked_connect)
    is_allowed_b, reason_b = parser.evaluate_event(ev_blocked)
    assert is_allowed_b is False
    assert reason_b is not None
    assert "EGRESS_PEP_BYPASS_ATTEMPT" in reason_b

    # Edge case: sock_arg without dport (dport is None) should not be blocked as port bypass
    no_port_connect = {
        "process_kprobe": {
            "process": {"pid": 102},
            "function_name": "sys_enter_connect",
            "args": [{"sock_arg": {"daddr": "127.0.0.1"}}],
        }
    }
    ev_no_port = parser.parse_raw_event(no_port_connect)
    is_allowed_np, _ = parser.evaluate_event(ev_no_port)
    assert is_allowed_np is True

    # Empty sock_arg
    empty_sock = {
        "process_kprobe": {
            "process": {"pid": 103},
            "function_name": "sys_enter_connect",
            "args": [{"sock_arg": {}}],
        }
    }
    ev_empty_sock = parser.parse_raw_event(empty_sock)
    is_allowed_es, _ = parser.evaluate_event(ev_empty_sock)
    assert is_allowed_es is True


def test_evaluate_file_access_and_lsm_enforcement() -> None:
    parser = TetragonEBPFStreamParser(SAMPLE_SPIFFE_ID, SAMPLE_DIGEST)

    # Blocked file access: /etc/shadow
    blocked_file = {
        "process_kprobe": {
            "process": {"pid": 200, "binary": "/bin/cat"},
            "function_name": "security_file_open",
            "args": [{"file_arg": {"path": "/etc/shadow"}}],
        }
    }
    ev_file = parser.parse_raw_event(blocked_file)
    is_allowed_f, reason_f = parser.evaluate_event(ev_file)
    assert is_allowed_f is False
    assert reason_f is not None
    assert "UNAUTHORIZED_CREDENTIAL_ACCESS_ATTEMPT" in reason_f

    # Allowed file access: regular workspace path
    allowed_file = {
        "process_kprobe": {
            "process": {"pid": 201, "binary": "/bin/cat"},
            "function_name": "security_file_open",
            "args": [{"file_arg": {"path": "/workspace/main.py"}}],
        }
    }
    ev_allowed_file = parser.parse_raw_event(allowed_file)
    is_allowed_norm, _ = parser.evaluate_event(ev_allowed_file)
    assert is_allowed_norm is True

    # LSM SIGKILL enforcement action
    lsm_kill = {
        "process_lsm": {
            "process": {"pid": 300},
            "function_name": "lsm_hook",
            "action": "LSM_ACTION_SIGKILL",
        }
    }
    ev_kill = parser.parse_raw_event(lsm_kill)
    is_allowed_k, reason_k = parser.evaluate_event(ev_kill)
    assert is_allowed_k is False
    assert reason_k is not None
    assert "LSM_ENFORCEMENT_ACTION" in reason_k


def test_evaluate_stream_lifecycle_and_receipt() -> None:
    parser = TetragonEBPFStreamParser(SAMPLE_SPIFFE_ID, SAMPLE_DIGEST)

    # Empty stream evaluation
    empty_receipt = parser.evaluate_stream("stream-empty-001", [])
    assert empty_receipt.total_events_evaluated == 0
    assert empty_receipt.allowed_events_count == 0
    assert empty_receipt.blocked_events_count == 0
    assert empty_receipt.integrity_score_bps == 10000  # claim: config
    assert empty_receipt.receipt_caid.startswith("sha256:")

    # Mixed stream evaluation (4 events: 3 allowed, 1 blocked)
    events = [
        # Allowed exec
        {
            "process_exec": {
                "process": {"pid": 10, "binary": "/bin/sh"},
            }
        },
        # Allowed gateway connect
        {
            "process_kprobe": {
                "process": {"pid": 11},
                "function_name": "sys_enter_connect",
                "args": [{"sock_arg": {"daddr": "127.0.0.1", "dport": 15001}}],
            }
        },
        # Allowed file open
        {
            "process_kprobe": {
                "process": {"pid": 12},
                "function_name": "sys_enter_openat",
                "args": [{"file_arg": {"path": "/app/src/index.js"}}],
            }
        },
        # Blocked credential open attempt
        {
            "process_kprobe": {
                "process": {"pid": 13, "binary": "/bin/grep"},
                "function_name": "security_file_open",
                "args": [{"file_arg": {"path": "/var/run/secrets/kubernetes.io/token"}}],
            }
        },
    ]

    receipt = parser.evaluate_stream("stream-batch-002", events)
    assert receipt.total_events_evaluated == 4
    assert receipt.allowed_events_count == 3
    assert receipt.blocked_events_count == 1
    # 1 out of 4 blocked = 2500 bps deduction -> 7500 bps
    assert receipt.integrity_score_bps == 7500
    assert len(receipt.policy_violations) == 1
    assert receipt.receipt_caid.startswith("sha256:")

    receipt_dict = receipt.to_dict()
    assert receipt_dict["integrity_score_bps"] == 7500
    assert receipt_dict["stream_id"] == "stream-batch-002"

    # L23 Anti-masking precision test: 11 events (1 allowed, 10 blocked)
    # (10 * 10000) // 11 = 9090 deduction -> 910 bps. Any +1 perturbation to 10000 yields 909 bps.
    eleven_events = [
        {"process_exec": {"process": {"pid": 1, "binary": "/bin/sh"}}}
    ] + [
        {
            "process_lsm": {
                "process": {"pid": idx + 2},
                "function_name": "lsm_hook",
                "action": "LSM_ACTION_SIGKILL",
            }
        }
        for idx in range(10)
    ]
    receipt_11 = parser.evaluate_stream("stream-11", eleven_events)
    assert receipt_11.total_events_evaluated == 11
    assert receipt_11.blocked_events_count == 10
    assert receipt_11.integrity_score_bps == 910

    # Profile digest mismatch check
    with pytest.raises(ValueError, match="ERR_BPF_PROFILE_MISMATCH"):
        parser.evaluate_stream(
            "stream-mismatch",
            events,
            stream_profile_digest="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        )
