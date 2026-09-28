"""Wraps generate_data.py, adapted to local-only: defaults to Ollama's OpenAI-compatible
endpoint instead of the script's own default (api.openai.com). Reaching a cloud endpoint
requires explicitly ticking 'Use cloud endpoint' -- never the default."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QSpinBox, QPushButton, QVBoxLayout, QWidget,
)

from paths import GROUPS_ROOT, KEV_ROOT, KEV_VENV_PY, LOCAL_GEN_API_KEY, LOCAL_GEN_BASE_URL, SKILL_SCRIPTS
from runner import ProcessRunner
from widgets import GroupCombo, PathPicker, sync_auto_path


class GenerateTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._auto: dict = {}
        layout = QVBoxLayout(self)

        def row(label, widget):
            r = QHBoxLayout()
            r.addWidget(QLabel(label))
            r.addWidget(widget)
            return r

        self.group_combo = GroupCombo()
        top = QHBoxLayout()
        top.addWidget(QLabel("Group:"))
        top.addWidget(self.group_combo)
        refresh_btn = QPushButton("Refresh groups")
        refresh_btn.clicked.connect(lambda: self.group_combo.refresh())
        top.addWidget(refresh_btn)
        top.addStretch()
        layout.addLayout(top)

        self.spec = PathPicker(filter_="JSON (*.json)")
        self.out = PathPicker(mode="save", filter_="JSON Lines (*.jsonl)")
        self.examples = PathPicker(filter_="JSON Lines (*.jsonl)")
        layout.addLayout(row("Workload spec:", self.spec))
        layout.addLayout(row("Output .jsonl:", self.out))
        layout.addLayout(row("Real examples (optional, style reference):", self.examples))

        self.cloud_checkbox = QCheckBox("Use cloud endpoint instead (default: local Ollama, nothing leaves this machine)")
        self.cloud_checkbox.toggled.connect(self._on_cloud_toggled)
        layout.addWidget(self.cloud_checkbox)

        self.base_url = QLineEdit(LOCAL_GEN_BASE_URL)
        self.api_key = QLineEdit(LOCAL_GEN_API_KEY)
        self.model = QLineEdit("qwen3.8:latest")
        layout.addLayout(row("Endpoint base URL:", self.base_url))
        layout.addLayout(row("API key:", self.api_key))
        layout.addLayout(row("Model:", self.model))

        self.n_records = QSpinBox(); self.n_records.setRange(1, 100000); self.n_records.setValue(600)
        self.batch = QSpinBox(); self.batch.setRange(1, 200); self.batch.setValue(20)
        self.concurrency = QSpinBox(); self.concurrency.setRange(1, 32); self.concurrency.setValue(4)
        self.seed = QSpinBox(); self.seed.setRange(0, 1_000_000)
        layout.addLayout(row("Records wanted (--n):", self.n_records))
        layout.addLayout(row("Batch size:", self.batch))
        layout.addLayout(row("Concurrency:", self.concurrency))
        layout.addLayout(row("Seed:", self.seed))

        self.dry_run = QCheckBox("Dry run (print one prompt, generate nothing -- fully offline either way)")
        layout.addWidget(self.dry_run)

        run_btn = QPushButton("Generate")
        run_btn.setObjectName("primary")
        run_btn.clicked.connect(self._run)
        layout.addWidget(run_btn)

        self.runner = ProcessRunner()
        layout.addWidget(self.runner)

        self.group_combo.refresh()
        self.group_combo.currentTextChanged.connect(self._on_group_changed)
        self._on_group_changed(self.group_combo.currentText())

    def _on_cloud_toggled(self, checked: bool) -> None:
        if checked:
            self.base_url.setText("https://api.openai.com/v1")
            self.api_key.clear()
            self.model.setText("gpt-4.1-mini")
        else:
            self.base_url.setText(LOCAL_GEN_BASE_URL)
            self.api_key.setText(LOCAL_GEN_API_KEY)
            self.model.setText("qwen3.8:latest")

    def _on_group_changed(self, group: str) -> None:
        if not group:
            return
        d = GROUPS_ROOT / group
        sync_auto_path(self.spec, self._auto, "spec", str(d / "workload.json"))
        sync_auto_path(self.out, self._auto, "out", str(d / "generated" / "generated.jsonl"))

    def _run(self) -> None:
        if self.cloud_checkbox.isChecked() and not self.api_key.text().strip():
            self.runner.append("[cloud endpoint selected but no API key given]\n")
            return
        args = [KEV_VENV_PY, SKILL_SCRIPTS / "generate_data.py", self.spec.text(),
                "--n", str(self.n_records.value()), "--model", self.model.text().strip(),
                "--base-url", self.base_url.text().strip(),
                "--batch", str(self.batch.value()), "--concurrency", str(self.concurrency.value()),
                "--seed", str(self.seed.value())]
        if self.dry_run.isChecked():
            args.append("--dry-run")
        else:
            if not self.out.text():
                self.runner.append("[set an output path first]\n")
                return
            args += ["--out", self.out.text()]
        if self.examples.text():
            args += ["--examples", self.examples.text()]
        env = {"KEV_GEN_API_KEY": self.api_key.text().strip() or "unused"}
        self.runner.run(args, cwd=KEV_ROOT, env_overrides=env)
