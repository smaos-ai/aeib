"""
AEIB Academic Reproduction Runner (Zone 1 Prototype)
Executes all verification suites in a single command and outputs an academic audit log.
"""

import sys
import subprocess
import json
import time

def run_suite():
    print("=" * 70)
    print("      AEIB INDEPENDENT ACADEMIC REPLICATION RUNNER")
    print("=" * 70)
    
    start = time.time()
    res = subprocess.run([
        sys.executable, "-m", "pytest",
        "tests/test_industrial_protection_matrix.py",
        "tests/test_ansi_50bf_breaker_failure.py",
        "tests/test_saga_compensation.py",
        "tests/test_falsifiability_matrix.py",
        "tests/test_research_mcp_adapter.py",
        "tests/test_chaos_petri_network_faults.py",
        "tests/test_human_review_console.py",
        "-q"
    ], capture_output=True, text=True)
    
    elapsed = time.time() - start
    
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_version": sys.version.split()[0],
        "exit_code": res.returncode,
        "elapsed_seconds": round(elapsed, 3),
        "status": "PASSED" if res.returncode == 0 else "FAILED",
        "pytest_summary": res.stdout.strip()
    }
    
    print(f"Status:          {report['status']}")
    print(f"Elapsed Time:    {report['elapsed_seconds']}s")
    print(f"Summary:         {report['pytest_summary']}")
    print("=" * 70)
    
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
        
    return res.returncode

if __name__ == "__main__":
    sys.exit(run_suite())
