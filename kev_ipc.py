"""Synchronous helpers for kevctl's --json query subcommands. Fast, read-only lookups only
(listing groups/trials, one-shot status) -- long-running actions (train/serve/evaluate) go
through runner.ProcessRunner instead, never through here."""
from __future__ import annotations

import json
import subprocess

from paths import KEVCTL, KEV_ROOT, KEV_VENV_PY


def _run_json(args: list) -> object:
    result = subprocess.run(
        [str(KEV_VENV_PY), str(KEVCTL), *args, "--json"],
        cwd=KEV_ROOT, capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"kevctl {' '.join(args)} failed (exit {result.returncode})")
    return json.loads(result.stdout)


def list_groups() -> list[dict]:
    return _run_json(["groups"])


def list_trials(group: str) -> list[dict]:
    return _run_json(["trials", "--group", group])


def server_status() -> dict:
    return _run_json(["status"])


def stage_file(group: str, data_path: str, allow_cross_group: bool = False) -> str:
    args = ["stage", "--group", group, "--data", data_path]
    if allow_cross_group:
        args.append("--allow-cross-group")
    return _run_json(args)["staged"]
