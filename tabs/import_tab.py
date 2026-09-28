"""Wraps extract_workload.py (scan a codebase for existing Jev/TypeSafe calls + labelled
data) and convert_data.py (CSV/TSV/JSONL of labels -> Kev records via column mapping)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from paths import GROUPS_ROOT, KEV_ROOT, KEV_VENV_PY, SKILL_SCRIPTS
from runner import ProcessRunner
from widgets import GroupCombo, PathPicker, sync_auto_path


class ImportTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._auto: dict = {}
        layout = QVBoxLayout(self)

        self.group_combo = GroupCombo()
        group_row = QHBoxLayout()
        group_row.addWidget(QLabel("Group:"))
        group_row.addWidget(self.group_combo)
        refresh_btn = QPushButton("Refresh groups")
        refresh_btn.clicked.connect(lambda: self.group_combo.refresh())
        group_row.addWidget(refresh_btn)
        group_row.addStretch()
        layout.addLayout(group_row)

        scan_box = QGroupBox("Scan a codebase for existing questions / labelled data")
        scan_form = QVBoxLayout(scan_box)
        self.scan_root = PathPicker(mode="dir")
        self.scan_out = PathPicker(mode="save", filter_="JSON (*.json)")
        row1 = QHBoxLayout(); row1.addWidget(QLabel("Codebase root:")); row1.addWidget(self.scan_root)
        row2 = QHBoxLayout(); row2.addWidget(QLabel("Write draft spec to:")); row2.addWidget(self.scan_out)
        scan_form.addLayout(row1)
        scan_form.addLayout(row2)
        scan_btn = QPushButton("Scan")
        scan_btn.setObjectName("primary")
        scan_btn.clicked.connect(self._run_scan)
        scan_form.addWidget(scan_btn)
        self.scan_runner = ProcessRunner()
        scan_form.addWidget(self.scan_runner)
        layout.addWidget(scan_box)

        convert_box = QGroupBox("Convert a CSV / TSV / JSONL of existing labels into Kev records")
        conv_form = QVBoxLayout(convert_box)
        self.conv_spec = PathPicker(filter_="JSON (*.json)")
        self.conv_data = PathPicker(filter_="Data files (*.csv *.tsv *.json *.jsonl)")
        self.conv_state_cols = QLineEdit()
        self.conv_state_cols.setPlaceholderText("e.g. subject,body (comma-separated column names)")
        self.conv_labels = QLineEdit()
        self.conv_labels.setPlaceholderText("QID=COLUMN, comma-separated, e.g. department=dept,escalate=urgent")
        self.conv_map = QLineEdit()
        self.conv_map.setPlaceholderText('optional renames: QID=FROM:TO,FROM:TO  (repeat blocks separated by ";")')
        self.conv_score_offset = QSpinBox()
        self.conv_score_offset.setRange(-10, 10)
        self.conv_out = PathPicker(mode="save", filter_="JSON Lines (*.jsonl)")

        def row(label, widget):
            r = QHBoxLayout()
            r.addWidget(QLabel(label))
            r.addWidget(widget)
            return r

        conv_form.addLayout(row("Workload spec:", self.conv_spec))
        conv_form.addLayout(row("Data file:", self.conv_data))
        conv_form.addLayout(row("State column(s):", self.conv_state_cols))
        conv_form.addLayout(row("Label mapping:", self.conv_labels))
        conv_form.addLayout(row("Rename map (optional):", self.conv_map))
        conv_form.addLayout(row("Score offset:", self.conv_score_offset))
        conv_form.addLayout(row("Output .jsonl:", self.conv_out))
        convert_btn = QPushButton("Convert")
        convert_btn.setObjectName("primary")
        convert_btn.clicked.connect(self._run_convert)
        conv_form.addWidget(convert_btn)
        self.conv_runner = ProcessRunner()
        conv_form.addWidget(self.conv_runner)
        layout.addWidget(convert_box)

        self.group_combo.refresh()
        self.group_combo.currentTextChanged.connect(self._on_group_changed)
        self._on_group_changed(self.group_combo.currentText())

    def _on_group_changed(self, group: str) -> None:
        if not group:
            return
        d = GROUPS_ROOT / group
        sync_auto_path(self.conv_spec, self._auto, "conv_spec", str(d / "workload.json"))
        sync_auto_path(self.conv_out, self._auto, "conv_out", str(d / "converted" / "converted.jsonl"))
        sync_auto_path(self.scan_out, self._auto, "scan_out", str(d / "workload_draft.json"))

    def _run_scan(self) -> None:
        root = self.scan_root.text()
        if not root:
            return
        args = [KEV_VENV_PY, SKILL_SCRIPTS / "extract_workload.py", root]
        if self.scan_out.text():
            args += ["--out", self.scan_out.text()]
        self.scan_runner.run(args, cwd=KEV_ROOT)

    def _run_convert(self) -> None:
        spec, data, state_cols, out = self.conv_spec.text(), self.conv_data.text(), self.conv_state_cols.text(), self.conv_out.text()
        if not (spec and data and state_cols and out):
            self.conv_runner.append("[fill in spec, data, state column(s) and output path first]\n")
            return
        args = [KEV_VENV_PY, SKILL_SCRIPTS / "convert_data.py", spec, data, "--state", state_cols, "--out", out]
        for pair in filter(None, (p.strip() for p in self.conv_labels.text().split(","))):
            args += ["--label", pair]
        for block in filter(None, (b.strip() for b in self.conv_map.text().split(";"))):
            args += ["--map", block]
        if self.conv_score_offset.value():
            args += ["--score-offset", str(self.conv_score_offset.value())]
        self.conv_runner.run(args, cwd=KEV_ROOT)
