"""Local ledger of every evaluate run, across every group/trial -- backs the Evaluate tab's
combined-results table. Pure JSON on disk; no network, no database.

Writes are atomic (write-to-temp-then-rename) and lock-guarded, so a crash mid-write can't
truncate the file and two processes appending at once can't silently drop one entry. A
corrupt file is quarantined on read rather than silently treated as empty -- otherwise the
next write would overwrite it with a fresh one-entry list and erase whatever was in it.
"""
from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path

from paths import EVAL_LEDGER_FILE

LOCK_FILE = EVAL_LEDGER_FILE.with_suffix(".lock")


def load() -> list[dict]:
    if not EVAL_LEDGER_FILE.exists():
        return []
    try:
        return json.loads(EVAL_LEDGER_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        _quarantine_corrupt_file()
        return []


def _quarantine_corrupt_file() -> None:
    """Rename a corrupt ledger aside instead of silently discarding it -- the next save()
    would otherwise overwrite it with a fresh list and the old entries would be gone for good."""
    if not EVAL_LEDGER_FILE.exists():
        return
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    quarantined = EVAL_LEDGER_FILE.with_name(f"{EVAL_LEDGER_FILE.stem}.corrupt-{stamp}.json")
    try:
        EVAL_LEDGER_FILE.rename(quarantined)
    except OSError:
        pass   # best-effort; a load() failure already means something's badly wrong with this directory


def save(entries: list[dict]) -> None:
    """Atomic on POSIX: write to a temp file in the same directory, then rename over the
    target. A crash mid-write leaves the OLD file intact rather than a truncated one."""
    EVAL_LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = EVAL_LEDGER_FILE.with_suffix(EVAL_LEDGER_FILE.suffix + ".tmp")
    tmp.write_text(json.dumps(entries, indent=2))
    os.replace(tmp, EVAL_LEDGER_FILE)


def add_entry(*, group: str, target: str, data: str, out_dir: str) -> dict | None:
    """Read out_dir/report.json (written by kev.benchmark) and append a summarized row.
    Lock-guarded end to end (load -> append -> save) so two evaluate runs finishing close
    together, in this process or another, can't race and silently drop each other's entry."""
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
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            entries = load()
            entries.append(entry)
            save(entries)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
    return entry
