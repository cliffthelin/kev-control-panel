"""Local ledger of every evaluate run, across every group/trial -- backs the Evaluate tab's
combined-results table. Pure JSON on disk; no network, no database."""
from __future__ import annotations

import json
import time
from pathlib import Path

from paths import EVAL_LEDGER_FILE


def load() -> list[dict]:
    if EVAL_LEDGER_FILE.exists():
        try:
            return json.loads(EVAL_LEDGER_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save(entries: list[dict]) -> None:
    EVAL_LEDGER_FILE.write_text(json.dumps(entries, indent=2))


def add_entry(*, group: str, target: str, data: str, out_dir: str) -> dict | None:
    """Read out_dir/report.json (written by kev.benchmark) and append a summarized row."""
    report_path = Path(out_dir) / "report.json"
    if not report_path.exists():
        return None
    try:
        report = json.loads(report_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    calibrated = report.get("calibrated_clean", {})
    entry = {
        "timestamp": time.time(),
        "group": group,
        "target": target,
        "data": data,
        "out_dir": str(out_dir),
        "n": calibrated.get("n"),
        "accuracy": calibrated.get("acc"),
        "brier": calibrated.get("brier"),
        "ece": calibrated.get("ece"),
        "coverage_at_5pct_error": calibrated.get("coverage_at_5pct_error"),
    }
    entries = load()
    entries.append(entry)
    save(entries)
    return entry
