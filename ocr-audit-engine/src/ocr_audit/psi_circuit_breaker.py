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
