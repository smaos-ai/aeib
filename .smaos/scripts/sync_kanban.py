#!/usr/bin/env python3
"""SMAOS Kanban Sync: Reads tasks from SQLite database and updates KANBAN.md"""
import sqlite3
import os
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = ".smaos/tasks.db"
KANBAN_PATH = ".smaos/KANBAN.md"

def sync_kanban_from_db():
    """Read tasks from SQLite database and update KANBAN.md"""
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found. Run 'cargo run --bin seed -p siss-decision-db' first.")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, title, status, stream, priority, assignee FROM tasks ORDER BY stream, priority DESC"
        )
        tasks = cursor.fetchall()
        conn.close()

        if not tasks:
            print(f"Warning: No tasks found in {DB_PATH}")
            return False

        kanban_content = f"""# KANBAN — Task Tracker (DB-Backed)
Last synced: {datetime.now().isoformat()}
Database: {DB_PATH}

## Status Key
- ⚫ Pending
- 🟠 In Progress
- ✅ Completed
- 📦 Archived

"""

        # Group tasks by stream
        streams = {}
        for task_id, title, status, stream, priority, assignee in tasks:
            if stream not in streams:
                streams[stream] = []
            status_icon = {
                "pending": "⚫",
                "in_progress": "🟠",
                "completed": "✅",
                "archived": "📦",
            }.get(status, "❓")

            assignee_str = f" (assignee: {assignee})" if assignee else ""
            task_line = f"- [{status_icon}] {task_id}: {title} (priority: {priority}){assignee_str}"
            streams[stream].append(task_line)

        # Write streams to KANBAN.md
        for stream in sorted(streams.keys()):
            stream_display = stream.upper().replace("_", " ")
            kanban_content += f"\n## {stream_display}\n"
            for task_line in streams[stream]:
                kanban_content += task_line + "\n"

        Path(KANBAN_PATH).write_text(kanban_content, "utf-8")
        print(f"✓ Synced {len(tasks)} tasks from {DB_PATH} to {KANBAN_PATH}")
        return True

    except sqlite3.Error as e:
        print(f"Error accessing database: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = sync_kanban_from_db()
    sys.exit(0 if success else 1)
