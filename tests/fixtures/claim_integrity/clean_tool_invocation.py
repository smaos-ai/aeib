"""Lean 4 proof runner that invokes `lake build` and reports verification results."""
import subprocess


def verify_proof(project_dir):
    proc = subprocess.run(["lake", "build"], cwd=project_dir, capture_output=True, text=True, check=False)
    return {"verified": proc.returncode == 0, "stderr": proc.stderr[-2000:]}
