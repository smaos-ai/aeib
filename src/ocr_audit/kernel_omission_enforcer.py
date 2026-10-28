# Copyright 2026 SovereignNexus Project
#
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

"""Anti-Omission Socket/Capsule Correlation Model (in-memory prototype)

Correlates caller-reported socket-connect events with caller-reported capsule
emissions inside a Python dict, and flags sockets that receive no matching
capsule ID within ``max_unregistered_delta_sec`` as
``SILENT_OMISSION_UNCACHED_EGRESS``.

SCOPE (honest label, 2026-10-26 audit): this is a user-space, in-memory model.
It does NOT attach eBPF programs, does NOT hook the kernel, and does NOT observe
real sockets — it only sees events that callers explicitly pass to
``register_socket_connect`` / ``register_capsule_emission``. State is lost on
process exit. It is not a DORA Art. 17 control by itself; any kernel-level
enforcement would require a separate eBPF component (scaffolding only in
``ebpf/``).
"""

import time
from typing import Any, Dict, List


class KernelOmissionEnforcer:
    def __init__(self, max_unregistered_delta_sec: float = 0.010):
        self.max_delta = max_unregistered_delta_sec
        self.active_sockets: Dict[str, float] = {}
        self.capsule_index: set = set()

    def register_socket_connect(self, socket_fd: int, remote_ip: str, port: int) -> str:
        sock_key = f"{socket_fd}:{remote_ip}:{port}"
        self.active_sockets[sock_key] = time.time()
        return sock_key

    def register_capsule_emission(self, capsule_id: str, sock_key: str) -> bool:
        if sock_key in self.active_sockets:
            elapsed = time.time() - self.active_sockets[sock_key]
            if elapsed <= self.max_delta:
                self.capsule_index.add(capsule_id)
                del self.active_sockets[sock_key]
                return True
        return False

    def audit_dangling_sockets(self) -> List[Dict[str, Any]]:
        now = time.time()
        dangling = []
        for sock_key, timestamp in list(self.active_sockets.items()):
            if now - timestamp > self.max_delta:
                dangling.append({
                    "socket": sock_key,
                    "violation": "SILENT_OMISSION_UNCACHED_EGRESS",
                    "latency_sec": round(now - timestamp, 6),
                })
        return dangling
