# Weekly GitHub Digest Setup — Sovereign Radar Integration

## Quick Start

### 1. Make Script Executable
```bash
chmod +x ~/.claude/scripts/weekly_github_digest.py
```

### 2. Run Manual Test
```bash
python3 ~/.claude/scripts/weekly_github_digest.py --output-dir ~/.smaos/briefings/
```

**Output:**
- `~/.smaos/briefings/weekly_digest_YYYYMMDD.md` — Markdown for Trojan Every Day
- `~/.smaos/briefings/weekly_digest_YYYYMMDD.json` — JSON for programmatic consumption

### 3. Schedule with Cron (Weekly, Monday 0600 UTC)

```bash
# Open crontab editor
crontab -e

# Add this line:
0 6 * * 1 /usr/bin/python3 ~/.claude/scripts/weekly_github_digest.py --output-dir ~/.smaos/briefings/
```

**To verify cron was set:**
```bash
crontab -l | grep weekly_github_digest
```

---

## Integration with Trojan Every Day (AwarenessCapsule)

Add to your daily ritual script (`~/.smaos/trojan_daily.py` or equivalent):

```python
from pathlib import Path
from datetime import datetime, timedelta

def load_weekly_digest() -> str:
    """Load latest weekly digest markdown into morning briefing."""
    briefing_dir = Path.home() / ".smaos" / "briefings"
    
    # Find latest digest (Monday's run, or most recent)
    digests = sorted(briefing_dir.glob("weekly_digest_*.md"), reverse=True)
    
    if digests:
        latest_digest = digests[0].read_text()
        return f"\n## Sovereign Radar — Latest Intelligence\n\n{latest_digest}\n"
    
    return ""

# In your AwarenessCapsule generation:
sovereign_radar = load_weekly_digest()
awareness_output = f"{morning_brief}\n{sovereign_radar}"
```

---

## Data Flow

```
Monday 0600 UTC
    ↓
Script runs via cron
    ↓
Clones/pulls 20 repos to ~/.smaos/repos/
    ↓
Extracts commits (last 7 days) via `git log`
    ↓
Groups by category (models, RAG, agents, runtime, compliance)
    ↓
Outputs:
  • weekly_digest_YYYYMMDD.md (for AwarenessCapsule)
  • weekly_digest_YYYYMMDD.json (for external tools)
    ↓
Trojan Every Day ritual loads MD file on Tuesday morning
    ↓
You see "Sovereign Radar" section in daily briefing with:
  - Highest-activity repos this week
  - Latest commits per category
  - New releases/tags
```

---

## Architecture: Local-First, No Cloud

✅ **Zero external API calls** — Uses local git clones only  
✅ **No GitHub API tokens needed** — Pure `git log` operations  
✅ **Fully offline after initial clone** — Repo updates require internet, but processing is local  
✅ **Cryptographic audit trail** — Can Merkle-hash digests + Ed25519-sign for EXEC_LOG  

**Storage footprint:**
- 20 repos @ shallow clone (depth=100) ≈ 2–3 GB total
- Updated weekly ≈ 50–100 MB network transfer

---

## Customization

### Add/Remove Repos

Edit `REPOS` dict in `weekly_github_digest.py`:

```python
REPOS = {
    "your_category": [
        ("owner/repo", "LICENSE", "description"),
        # ...
    ],
}
```

### Change Schedule

Cron examples:
- **Daily**: `0 6 * * *`
- **Weekly (Friday)**: `0 6 * * 5`
- **Bi-weekly**: `0 6 * * 1 if ($(date +%W) % 2) == 0; then ...`

### Change Lookback Window

```bash
python3 ~/.claude/scripts/weekly_github_digest.py --days 14
```

---

## Troubleshooting

### Script runs but no output
```bash
# Check if repos are cloning
ls -la ~/.smaos/repos/

# Run with verbose output
python3 ~/.claude/scripts/weekly_github_digest.py --output-dir ~/.smaos/briefings/
```

### Cron not running
```bash
# Check cron logs (macOS)
log stream --predicate 'process == "cron"' --level debug

# Check if cron daemon is running
ps aux | grep cron
```

### Git errors (timeout, auth)
The script uses `--depth=100` to limit clone size. If a repo is huge:
```bash
# Increase depth or remove the flag
# Edit: git clone --depth=1000 (instead of 100)
```

---

## Security & Covenant Alignment

✅ **Local-first execution:** No data leaves your machine  
✅ **Audit trail:** Output can be Merkle-rooted + signed  
✅ **No extraction:** You own the digest, not a SaaS vendor  
✅ **Transparent sources:** 20 repos, all open-source, all checksummed  

**To cryptographically sign the digest:**
```bash
# Add to cron post-script or Trojan Daily ritual
cd ~/.smaos/briefings/
sha256sum weekly_digest_*.md >> ~/.smaos/exec/EXEC_LOG.json
security find-generic-password -s "axiom:ed25519:architect" -w | \
  openssl dgst -sha256 -sign - weekly_digest_*.md | base64 >> ~/.smaos/briefings/latest_digest.sig
```

---

## Expected First Run Output

```
[2026-06-04T09:30:00Z] Starting weekly digest collection...
Output: /Users/andriileukhin/.smaos/briefings

[open_weight_models]
  1/20: deepseek-ai/DeepSeek-V4... ✓ (12 commits)
  2/20: QwenLM/Qwen3... ✓ (8 commits)
  ...

[eu_compliance]
  19/20: slundberg/shap... ✓ (3 commits)
  20/20: sktime/sktime... ✓ (5 commits)

✅ Markdown digest: /Users/andriileukhin/.smaos/briefings/weekly_digest_20260604.md
✅ JSON digest: /Users/andriileukhin/.smaos/briefings/weekly_digest_20260604.json

======================================================================
SOVEREIGN RADAR SUMMARY
======================================================================
# Sovereign Radar — Weekly GitHub Digest
**Generated:** 2026-06-04 09:30 UTC
**Coverage:** Last 7 days across 20 critical repos

## 🚨 Highest-Activity Repos (This Week)

**DeepSeek-V4** (12 commits) — Latest: feat: add quantization support for 4-bit weights
**Qwen3** (8 commits) — Release: Qwen3-32B-Instruct-v1.0.1
...
```

---

## Next: Full Trojan Every Day Integration

Once this runs weekly, integrate into your 7-minute daily ritual:

```
Morning (7 min total):
├─ Load AwarenessCapsule (OSINT + scientific + geopolitical)
├─ Load Sovereign Radar digest (yesterday's ecosystem movement)
├─ Compute γ-confidence scores
├─ Make today's decision with full competitive context
└─ Log to EXEC_LOG with Merkle proof
```

**Result:** Every morning, you see not just what happened in the world, but what's happening in the global AI ecosystem—without duplicating a single line of code.

---

**Status:** ✅ **SOVEREIGN RADAR READY TO DEPLOY**
