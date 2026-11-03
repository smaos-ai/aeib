import json
from pathlib import Path

from tools.transcript_cost_report import main, summarize


def _write(tmp_path: Path) -> Path:
    rows = [
        {"source": "MODEL", "type": "GENERIC", "created_at": "2026-11-02T15:01:00Z", "content": "a" * 100},
        {"source": "SYSTEM", "type": "SYSTEM_MESSAGE", "created_at": "2026-11-02T15:30:00Z"},
        {"source": "SYSTEM", "type": "SYSTEM_MESSAGE", "created_at": "2026-11-02T16:02:00Z"},
    ]
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n\n[1]\n", encoding="utf-8")
    return p


def test_summarize_counts_bytes_wakeups_and_malformed(tmp_path: Path):
    r = summarize(_write(tmp_path))
    assert r["malformed_lines"] == 2
    assert r["by_step_type"]["SYSTEM/SYSTEM_MESSAGE"]["steps"] == 2
    assert r["by_step_type"]["MODEL/GENERIC"]["steps"] == 1
    assert r["system_wakeups_per_hour"] == {"2026-11-02T15": 1, "2026-11-02T16": 1}
    shares = sum(v["share_bps"] for v in r["by_step_type"].values())
    assert 9998 <= shares <= 10000
    assert r["total_bytes"] == sum(v["bytes"] for v in r["by_step_type"].values())


def test_cli_missing_file_and_json(tmp_path: Path, capsys):
    assert main([str(tmp_path / "nope.jsonl")]) == 2
    assert main([str(_write(tmp_path)), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["malformed_lines"] == 2
