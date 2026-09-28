"""Wraps `kevctl train`: scratch-trial fine-tuning, group-isolated, hard-offline by default."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

import kev_ipc
from paths import DEFAULT_BASE, DEFAULT_GPU, DEFAULT_RUN, KEVCTL, KEV_ROOT, KEV_VENV_PY
from runner import ProcessRunner
from widgets import GroupCombo, PathPicker


def _row(label, widget):
    r = QHBoxLayout()
    r.addWidget(QLabel(label))
    r.addWidget(widget)
    return r


class TrainTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.group_combo = GroupCombo()
        top = QHBoxLayout()
        top.addWidget(QLabel("Group:"))
        top.addWidget(self.group_combo)
        refresh_btn = QPushButton("Refresh groups")
        refresh_btn.clicked.connect(lambda: self.group_combo.refresh())
        top.addWidget(refresh_btn)
        top.addStretch()
        layout.addLayout(top)

        self.data = PathPicker(filter_="JSON Lines (*.jsonl)")
        self.base = QLineEdit(DEFAULT_BASE)
        self.init_from = QLineEdit(DEFAULT_RUN)
        self.epochs = QSpinBox(); self.epochs.setRange(1, 100); self.epochs.setValue(2)
        self.lr = QDoubleSpinBox(); self.lr.setDecimals(6); self.lr.setRange(0.0, 1.0); self.lr.setSingleStep(0.00001); self.lr.setValue(0.00002)
        self.batch = QSpinBox(); self.batch.setRange(1, 64); self.batch.setValue(1)
        self.accum = QSpinBox(); self.accum.setRange(1, 256); self.accum.setValue(8)
        self.gpu = QSpinBox(); self.gpu.setRange(0, 8); self.gpu.setValue(DEFAULT_GPU)
        self.extra = QLineEdit()
        self.extra.setPlaceholderText("extra kev.train flags, e.g. --max_steps 1")
        self.allow_cross_group = QCheckBox("Allow --data / --init-from from a different group (blocked by default)")

        layout.addLayout(_row("Data (.jsonl):", self.data))
        layout.addLayout(_row("Base model:", self.base))
        layout.addLayout(_row("Warm-start from (--init-from):", self.init_from))
        layout.addLayout(_row("Epochs:", self.epochs))
        layout.addLayout(_row("Learning rate:", self.lr))
        layout.addLayout(_row("Batch:", self.batch))
        layout.addLayout(_row("Accumulation steps:", self.accum))
        layout.addLayout(_row("GPU index:", self.gpu))
        layout.addLayout(_row("Extra flags:", self.extra))
        layout.addWidget(self.allow_cross_group)

        run_btn = QPushButton("Train (new scratch trial)")
        run_btn.setObjectName("primary")
        run_btn.clicked.connect(self._run)
        layout.addWidget(run_btn)

        self.runner = ProcessRunner()
        self.runner.finished.connect(self._on_finished)
        layout.addWidget(self.runner)

        self.group_combo.refresh()

    def _run(self) -> None:
        group = self.group_combo.currentText()
        if not group or not self.data.text():
            self.runner.append("[pick a group and a data file first]\n")
            return

        try:
            status = kev_ipc.server_status()
        except RuntimeError as e:
            status = None
            self.runner.append(f"[could not check server status: {e}]\n")
        if status and status["server"].get("running") and status["server"].get("meta", {}).get("gpu") == self.gpu.value():
            if QMessageBox.question(
                self, "Server is using this GPU",
                f"The Kev server is currently running on GPU {self.gpu.value()} and training needs that VRAM too.\n"
                "Stop it and continue?",
            ) != QMessageBox.Yes:
                return

        args = [KEV_VENV_PY, KEVCTL, "train", "--group", group, "--data", self.data.text(),
                "--base", self.base.text().strip(), "--epochs", str(self.epochs.value()),
                "--lr", str(self.lr.value()), "--batch", str(self.batch.value()),
                "--accum", str(self.accum.value()), "--gpu", str(self.gpu.value()), "--yes"]
        if self.init_from.text().strip() != DEFAULT_RUN:
            args += ["--init-from", self.init_from.text().strip()]
        if self.allow_cross_group.isChecked():
            args.append("--allow-cross-group")
        if self.extra.text().strip():
            args += ["--"] + self.extra.text().strip().split()
        self.runner.run(args, cwd=KEV_ROOT)

    def _on_finished(self, code: int) -> None:
        if code == 0:
            self.runner.append("\n[trial saved -- see the Serve tab to try it, or the Evaluate tab to score it]\n")
