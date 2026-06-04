#!/usr/bin/env python3
"""
Weekly GitHub Digest — Sovereign Radar for Mission100/Axiom Protocol
Pulls latest commits from 20 critical repos into Trojan Every Day briefing.
Local-first execution; no cloud dependency.

Usage:
  python3 weekly_github_digest.py [--output-dir /path]

Cron (weekly, Monday 0600 UTC):
  0 6 * * 1 /usr/bin/python3 /path/to/weekly_github_digest.py --output-dir ~/.smaos/briefings/
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


# 20-REPO WATCHLIST — Grouped by Strategic Gap
REPOS = {
    "open_weight_models": [
        ("deepseek-ai/DeepSeek-V4", "MIT", "frontier model, coding #1"),
        ("QwenLM/Qwen3", "Apache 2.0", "open-weight baseline, 100k+ forks"),
        ("QwenLM/Qwen3-Coder", "Apache 2.0", "coding specialization"),
        ("meta-llama/llama-models", "LLAMA2", "US baseline, Llama 4"),
        ("google-deepmind/gemma", "Apache 2.0", "native audio/vision, 12B"),
    ],
    "enterprise_rag": [
        ("infiniflow/ragflow", "Apache 2.0", "deep parsing, OCR, 81k stars"),
        ("labring/FastGPT", "Apache 2.0", "visual RAG, production Docker"),
        ("run-llama/llama_index", "MIT", "modular RAG, US baseline"),
        ("langchain-ai/langchain", "MIT", "agent + RAG orchestration"),
    ],
    "agent_frameworks": [
        ("Significant-Gravitas/AutoGPT", "MIT", "autonomous tasks, 175k stars"),
        ("openclaw/openclaw", "Apache 2.0", "cross-platform agents, 79k stars"),
        ("1Panel-dev/MaxKB", "Apache 2.0", "one-click agent deploy"),
        ("FlowiseAI/Flowise", "MIT", "visual workflow builder"),
        ("langgenius/dify", "Apache 2.0", "LLM app framework"),
    ],
    "local_runtime": [
        ("ollama/ollama", "MIT", "one-command local LLMs, 148k stars"),
        ("ggml-org/llama.cpp", "MIT", "CPU/GPU quantization, 90k stars"),
        ("vllm-project/vllm", "Apache 2.0", "high-throughput inference"),
    ],
    "eu_compliance": [
        ("slundberg/shap", "MIT", "explainability standard"),
        ("pgmpy/pgmpy", "Apache 2.0", "causal inference"),
        ("sktime/sktime", "BSD-3", "time-series ML, ESoC-funded"),
    ],
}


def run_git_command(cmd: list[str], cwd: Optional[Path] = None) -> str:
    """Execute git command, return stdout."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT: {' '.join(cmd)}]"
    except Exception as e:
        return f"[ERROR: {str(e)}]"


def fetch_repo_digest(owner: str, repo: str, days: int = 7) -> dict:
    """Fetch commit digest for one repo via git (no API token needed)."""
    repo_path = Path.home() / ".smaos" / "repos" / owner / repo
    repo_path.parent.mkdir(parents=True, exist_ok=True)

    # Clone or update repo
    if repo_path.exists():
        run_git_command(["git", "fetch", "--all"], cwd=repo_path)
    else:
        run_git_command(
            ["git", "clone", "--depth=100", f"https://github.com/{owner}/{repo}.git", str(repo_path)],
            cwd=repo_path.parent,
        )

    # Get commits from last N days
    since_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
    log_output = run_git_command(
        [
            "git",
            "log",
            "--oneline",
            "--no-decorate",
            f"--since={since_date}",
            "--author-date=short",
        ],
        cwd=repo_path,
    )

    commits = [line.strip() for line in log_output.split("\n") if line.strip()]
    commit_count = len(commits)

    # Get latest tag/release info
    tags = run_git_command(["git", "tag", "--sort=-version:refname", "--limit=3"], cwd=repo_path)

    return {
        "owner": owner,
        "repo": repo,
        "full_name": f"{owner}/{repo}",
        "commits_last_7d": commit_count,
        "latest_commits": commits[:5],  # Top 5 most recent
        "latest_tags": tags.split("\n")[:3],
        "fetched_at": datetime.utcnow().isoformat(),
    }


def generate_digest_markdown(digests: dict) -> str:
    """Format digests into Trojan Every Day briefing format."""

    output = [
        "# Sovereign Radar — Weekly GitHub Digest",
        f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Coverage:** Last 7 days across 20 critical repos",
        "",
        "## 🚨 Highest-Activity Repos (This Week)",
        "",
    ]

    # Sort by commit count
    sorted_by_activity = sorted(
        digests.values(),
        key=lambda x: x["commits_last_7d"],
        reverse=True,
    )

    for digest in sorted_by_activity[:5]:
        output.append(
            f"**{digest['repo']}** ({digest['commits_last_7d']} commits) — {digest['latest_commits'][0] if digest['latest_commits'] else 'No recent commits'}"
        )

    output.extend(["", "## 📊 Activity by Category", ""])

    # Regroup and summarize by category
    for category, repos_list in REPOS.items():
        output.append(f"### {category.replace('_', ' ').title()}")
        output.append("")

        for owner, repo, license_type, description in repos_list:
            full_name = f"{owner}/{repo}"
            if full_name in digests:
                digest = digests[full_name]
                commits = digest["commits_last_7d"]
                tag_info = f" | Latest: {digest['latest_tags'][0]}" if digest['latest_tags'] else ""
                output.append(
                    f"- **{repo}** ({license_type}) — {commits} commits{tag_info}"
                )
                if digest["latest_commits"]:
                    output.append(f"  > {digest['latest_commits'][0]}")

        output.append("")

    output.extend([
        "## 🔒 Data Integrity",
        f"- Script executed locally on {datetime.utcnow().strftime('%Y-%m-%d')}",
        "- All repos cloned to `~/.smaos/repos/` (no external API calls required)",
        "- Ready to feed to AwarenessCapsule for daily briefing",
        "",
        "---",
        "**Next digest:** Next Monday 0600 UTC",
    ])

    return "\n".join(output)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate weekly GitHub digest for Trojan Every Day")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / ".smaos" / "briefings",
        help="Output directory for digest",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{datetime.utcnow().isoformat()}] Starting weekly digest collection...")
    print(f"Output: {args.output_dir}")
    print()

    # Fetch all repos
    digests = {}
    total_repos = sum(len(repos) for repos in REPOS.values())
    processed = 0

    for category, repos_list in REPOS.items():
        print(f"\n[{category}]")
        for owner, repo, _, description in repos_list:
            processed += 1
            full_name = f"{owner}/{repo}"
            try:
                print(f"  {processed}/{total_repos}: {full_name}...", end=" ", flush=True)
                digest = fetch_repo_digest(owner, repo, days=args.days)
                digests[full_name] = digest
                print(f"✓ ({digest['commits_last_7d']} commits)")
            except Exception as e:
                print(f"✗ ({str(e)})")

    # Generate markdown
    markdown = generate_digest_markdown(digests)
    markdown_path = args.output_dir / f"weekly_digest_{datetime.utcnow().strftime('%Y%m%d')}.md"
    markdown_path.write_text(markdown)
    print(f"\n✅ Markdown digest: {markdown_path}")

    # Generate JSON for programmatic consumption
    json_path = args.output_dir / f"weekly_digest_{datetime.utcnow().strftime('%Y%m%d')}.json"
    json_path.write_text(json.dumps(digests, indent=2))
    print(f"✅ JSON digest: {json_path}")

    # Print summary
    print(f"\n{'='*70}")
    print(f"SOVEREIGN RADAR SUMMARY")
    print(f"{'='*70}")
    print(markdown)

    return 0


if __name__ == "__main__":
    sys.exit(main())
