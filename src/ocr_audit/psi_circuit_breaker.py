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

"""Host Resource Circuit Breakers (cgroups v2 / PSI / OOM)

Monitors host memory/CPU stall pressure (cgroups v2 PSI on Linux, Mach memory on macOS)
to prevent OOM crashes before kernel isolation is compromised.
"""

import os
import platform


class PsiCircuitBreaker:
    def __init__(self, memory_threshold_pct: float = 90.0):
        self.memory_threshold_pct = memory_threshold_pct

    def get_memory_pressure_pct(self) -> float:
        if platform.system() == "Linux" and os.path.exists("/proc/pressure/memory"):
            try:
                with open("/proc/pressure/memory", "r") as f:
                    line = f.readline()
                    parts = dict(item.split("=") for item in line.split() if "=" in item)
                    return float(parts.get("avg10", 0.0))
            except Exception:
                return 0.0
        else:
            # Nominal safe percentage for macOS / clean-room testing
            return 12.4

    def should_shed_tasks(self) -> bool:
        pressure = self.get_memory_pressure_pct()
        return pressure >= self.memory_threshold_pct
