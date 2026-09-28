"""Wraps split_data.py (validate + split into train/calibration/development) and
plan_size.py (how much data is needed to detect a meaningful gain)."""
from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from paths import GROUPS_ROOT, KEV_ROOT, KEV_VENV_PY, SKILL_SCRIPTS
from runner import ProcessRunner
from widgets import GroupCombo, PathPicker, sync_auto_path


def _row(label, widget):
    r = QHBoxLayout()
    r.addWidget(QLabel(label))
    r.addWidget(widget)
    return r


class ValidateTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._auto: dict = {}
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

        split_box = QGroupBox("Validate + split (split_data.py)")
        split_form = QVBoxLayout(split_box)
        self.split_data = PathPicker(filter_="JSON Lines (*.jsonl)")
        self.split_out = PathPicker(mode="dir")
        self.split_holdout = PathPicker(filter_="JSON Lines (*.jsonl)")
        self.calibration_frac = QDoubleSpinBox(); self.calibration_frac.setRange(0.0, 0.9); self.calibration_frac.setSingleStep(0.05); self.calibration_frac.setValue(0.15)
        self.development_frac = QDoubleSpinBox(); self.development_frac.setRange(0.0, 0.9); self.development_frac.setSingleStep(0.05); self.development_frac.setValue(0.15)
        split_form.addLayout(_row("Data (.jsonl):", self.split_data))
        split_form.addLayout(_row("Output dir:", self.split_out))
        split_form.addLayout(_row("Holdout real data (optional):", self.split_holdout))
        split_form.addLayout(_row("Calibration fraction:", self.calibration_frac))
        split_form.addLayout(_row("Development fraction:", self.development_frac))
        split_btn = QPushButton("Validate + Split")
        split_btn.setObjectName("primary")
        split_btn.clicked.connect(self._run_split)
        split_form.addWidget(split_btn)
        self.split_runner = ProcessRunner()
        split_form.addWidget(self.split_runner)
        layout.addWidget(split_box)

        plan_box = QGroupBox("Plan size (plan_size.py) -- how much data before you bother training")
        plan_form = QVBoxLayout(plan_box)
        self.plan_spec = PathPicker(filter_="JSON (*.json)")
        self.plan_baseline = QDoubleSpinBox(); self.plan_baseline.setRange(0.0, 1.0); self.plan_baseline.setSingleStep(0.05); self.plan_baseline.setValue(0.75)
        self.plan_min_gain = QDoubleSpinBox(); self.plan_min_gain.setRange(0.0, 1.0); self.plan_min_gain.setSingleStep(0.01); self.plan_min_gain.setValue(0.05)
        plan_form.addLayout(_row("Workload spec:", self.plan_spec))
        plan_form.addLayout(_row("Expected baseline accuracy:", self.plan_baseline))
        plan_form.addLayout(_row("Smallest gain worth detecting:", self.plan_min_gain))
        plan_btn = QPushButton("Plan")
        plan_btn.setObjectName("primary")
        plan_btn.clicked.connect(self._run_plan)
        plan_form.addWidget(plan_btn)
        self.plan_runner = ProcessRunner()
        plan_form.addWidget(self.plan_runner)
        layout.addWidget(plan_box)

        self.group_combo.refresh()
        self.group_combo.currentTextChanged.connect(self._on_group_changed)
        self._on_group_changed(self.group_combo.currentText())

    def _on_group_changed(self, group: str) -> None:
        if not group:
            return
        d = GROUPS_ROOT / group
        sync_auto_path(self.split_out, self._auto, "split_out", str(d / "splits" / "default"))
        sync_auto_path(self.plan_spec, self._auto, "plan_spec", str(d / "workload.json"))

    def _run_split(self) -> None:
        if not self.split_data.text():
            self.split_runner.append("[pick a data file first]\n")
            return
        args = [KEV_VENV_PY, SKILL_SCRIPTS / "split_data.py", self.split_data.text(),
                "--calibration", str(self.calibration_frac.value()), "--development", str(self.development_frac.value())]
        if self.split_out.text():
            args += ["--out", self.split_out.text()]
        if self.split_holdout.text():
            args += ["--holdout", self.split_holdout.text()]
        self.split_runner.run(args, cwd=KEV_ROOT)

    def _run_plan(self) -> None:
        args = [KEV_VENV_PY, SKILL_SCRIPTS / "plan_size.py"]
        if self.plan_spec.text():
            args.append(self.plan_spec.text())
        args += ["--baseline-acc", str(self.plan_baseline.value()), "--min-gain", str(self.plan_min_gain.value())]
        self.plan_runner.run(args, cwd=KEV_ROOT)
