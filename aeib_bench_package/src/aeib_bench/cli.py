"""aeib-bench: thin CLI over the in-repo AEIB execution-integrity harness.

Every number printed here is computed by running the harness. Nothing is
hardcoded. Repo-only for now (not published to PyPI).
"""
import argparse
import importlib.util
import json
import statistics
import sys
from pathlib import Path

HARNESS_REL = Path("benchmarks/aeib_execution_integrity/run_episodes.py")


def _find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / HARNESS_REL).is_file():
            return p
    raise FileNotFoundError(
        f"Could not locate {HARNESS_REL} above {start}. Run aeib-bench from inside the AEIB repository."
    )


def _load_harness(root: Path):
    spec = importlib.util.spec_from_file_location("aeib_run_episodes", root / HARNESS_REL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the AEIB 4-arm duplicate-mutation benchmark.")
    ap.add_argument("--episodes", type=int, default=500)
    ap.add_argument("--seeds", type=str, default="42", help="Comma list or range a-b, e.g. 1-20")
    ap.add_argument("--json", type=str, default=None, help="Write per-seed results to this path")
    args = ap.parse_args(argv)

    if "-" in args.seeds:
        a, b = (int(x) for x in args.seeds.split("-"))
        seeds = list(range(a, b + 1))
    else:
        seeds = [int(s) for s in args.seeds.split(",")]

    harness = _load_harness(_find_repo_root(Path.cwd().resolve()))
    arms = ["naive_retry_baseline", "payload_derived_key", "server_side_stable_key", "aeib"]
    per_seed = []
    failures = []
    for s in seeds:
        try:
            rep = harness.run_all_episodes(seed=s, count=args.episodes)
        except AssertionError as e:
            # Harness invariant broke for this seed: report it, do not hide it.
            failures.append({"seed": s, "error": str(e)})
            continue
        per_seed.append({"seed": s, **{a: rep["results"][a]["duplicate_mutations"] for a in arms},
                         "aeib_unresolved": rep["results"]["aeib"].get("unresolved_episodes"),
                         "server_unresolved": rep["results"]["server_side_stable_key"].get("unresolved_episodes")})

    print("\n" + "=" * 72)
    print(f"aeib-bench summary: {len(per_seed)}/{len(seeds)} seeds completed, {args.episodes} episodes each")
    print("(deterministic simulation; not live network traffic)")
    print("=" * 72)
    for a in arms:
        vals = [r[a] for r in per_seed]
        if vals:
            print(f"{a:26s} duplicates  mean={statistics.mean(vals):7.2f}  min={min(vals):4d}  max={max(vals):4d}")
    for f in failures:
        print(f"[FAIL] seed={f['seed']}: {f['error']}")

    if args.json:
        Path(args.json).write_text(json.dumps({"per_seed": per_seed, "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
