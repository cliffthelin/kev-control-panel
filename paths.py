"""Shared paths and constants for the Kev control-panel GUI."""
from pathlib import Path

GUI_ROOT = Path(__file__).resolve().parent
KEV_ROOT = GUI_ROOT.parent
KEV_VENV_PY = KEV_ROOT / ".venv" / "bin" / "python"
KEVCTL = KEV_ROOT / "kevctl.py"
GROUPS_ROOT = KEV_ROOT / "groups"
SKILL_SCRIPTS = KEV_ROOT / "skills" / "kev-finetune" / "scripts"
ASSETS = KEV_ROOT / "skills" / "kev-finetune" / "assets"

GUI_STATE = GUI_ROOT / "state"
GUI_STATE.mkdir(exist_ok=True)
SOURCES_FILE = GUI_STATE / "group_sources.json"    # registered external folders per group (GUI-only bookmarks)
EVAL_LEDGER_FILE = GUI_STATE / "eval_runs.json"     # combined-results ledger across every evaluate run

DATA_EXTENSIONS = {".csv", ".tsv", ".json", ".jsonl", ".ndjson"}

# kevctl already sets these for train/serve; the GUI applies the same policy to every
# subprocess it launches that could otherwise reach huggingface.co on its own.
OFFLINE_ENV = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
}

DEFAULT_GPU = 1
DEFAULT_PORT = 8010
DEFAULT_RUN = "jaredpalmer/kev-9b"
DEFAULT_BASE = "Qwen/Qwen3.5-9B-Base"

# Local-only default for generate_data.py: Ollama's OpenAI-compatible endpoint, not the
# script's own default (api.openai.com). The Generate tab requires an explicit opt-in
# checkbox before it will use anything else.
LOCAL_GEN_BASE_URL = "http://localhost:11434/v1"
LOCAL_GEN_API_KEY = "ollama"   # Ollama ignores the value; the OpenAI wire format still requires one
