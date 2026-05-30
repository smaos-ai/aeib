#!/usr/bin/env python3
"""SMAOS Kanban Sync: Extracts task changes from session logs, updates KANBAN.md, appends Merkle proof."""
import json
import hashlib
import sys
import re
import os
from pathlib import Path
from datetime import datetime

KANBAN_PATH = Path(".smaos/KANBAN.md")
EXEC_LOG_PATH = Path(".smaos/exec/EXEC_LOG.json")
SESSION_LOG_ENV = os.getenv("CLAUDE_SESSION_LOG")


def compute_merkle(content: str) -> str:
    """Compute SHA256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_session_changes(log_path: str | None) -> list[dict]:
    """Extract task status changes and brainstorm snippets from session log."""
    if not log_path or not Path(log_path).exists():
        return []

    try:
        text = Path(log_path).read_text("utf-8", errors="ignore")
    except Exception:
        return []

    changes = []

    # Extract explicit task markers: [TASK:ID] -> STATUS
    for m in re.finditer(r"\[TASK:(IL-\d+|DB-\d+)\]\s*->\s*(\w+)", text):
        changes.append({
            "id": m.group(1),
            "new_status": m.group(2),
            "source": "explicit"
        })

    # Extract brainstorm snippets
    for m in re.finditer(r"(?:brainstorm|BRAINSTORM):\s*(.+)", text):
        changes.append({
            "type": "brainstorm",
            "content": m.group(1).strip(),
            "source": "voice_text"
        })

    return changes


def update_kanban(changes: list[dict]) -> bool:
    """Update KANBAN.md with status changes and brainstorm entries."""
    if not changes:
        return False

    try:
        kanban = KANBAN_PATH.read_text("utf-8")
    except Exception:
        return False

    # Process explicit task status changes
    for ch in changes:
        if ch.get("source") == "explicit":
            task_id = ch["id"]
            new_status = ch["new_status"]
            # Simple replacement: find row and update status column
            pattern = rf"(\| `{re.escape(task_id)}` \|.*?\|)\s*`\w+`\s*(\|)"
            replacement = rf"\1 `{new_status}` \2"
            kanban = re.sub(pattern, replacement, kanban)

    # Append brainstorm log if any brainstorms present
    brainstorms = [c for c in changes if c.get("type") == "brainstorm"]
    if brainstorms:
        timestamp = datetime.utcnow().isoformat()
        brain_section = f"\n**Session {timestamp}:**\n"
        for b in brainstorms:
            brain_section += f"- {b['content']}\n"
        kanban += brain_section

    try:
        KANBAN_PATH.write_text(kanban, "utf-8")
        return True
    except Exception:
        return False


def append_merkle_audit() -> str:
    """Compute Merkle hash of current KANBAN.md and log to EXEC_LOG.json."""
    try:
        current = KANBAN_PATH.read_text("utf-8")
    except Exception:
        return "error"

    root = compute_merkle(current)
    entry = {
        "event": "kanban_sync",
        "timestamp": datetime.utcnow().isoformat(),
        "merkle_root": root,
        "source": "sync_kanban.py"
    }

    try:
        EXEC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if EXEC_LOG_PATH.exists():
            try:
                entries = json.loads(EXEC_LOG_PATH.read_text("utf-8") or "[]")
            except Exception:
                entries = []
        else:
            entries = []

        entries.append(entry)
        EXEC_LOG_PATH.write_text(json.dumps(entries, indent=2), "utf-8")
        return root
    except Exception:
        return "error"


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "manual"
    log_path = SESSION_LOG_ENV

    # Parse additional args for log path
    for i, arg in enumerate(sys.argv):
        if arg == "--log" and i + 1 < len(sys.argv):
            log_path = sys.argv[i + 1]
        elif arg.startswith("--log="):
            log_path = arg.split("=", 1)[1]

    changes = parse_session_changes(log_path)

    if update_kanban(changes):
        root = append_merkle_audit()
        print(f"✅ Kanban synced. Merkle: {root[:12]}...")
    else:
        if changes:
            print(f"⚠️ Changes detected but sync failed. Changes: {len(changes)}")
        else:
            print("ℹ️ No changes to sync.")
