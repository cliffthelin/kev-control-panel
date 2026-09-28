"""Wraps kev.benchmark (score a local checkpoint or a running server) and kev.compare
(paired-bootstrap comparison between two runs), plus the combined-results ledger -- the
'response tracker' linking every evaluate run back to its group/trial."""
from __future__ import annotations

import json
import time
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QRadioButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

import results_store
from paths import DEFAULT_GPU, DEFAULT_PORT, DEFAULT_RUN, GROUPS_ROOT, KEV_ROOT, KEV_VENV_PY, OFFLINE_ENV
from runner import ProcessRunner
from widgets import GroupCombo, PathPicker, sync_auto_path


def _row(label, widget):
    r = QHBoxLayout()
    r.addWidget(QLabel(label))
    r.addWidget(widget)
    return r


class ReportDialog(QDialog):
    def __init__(self, report: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("report.json")
        self.resize(700, 600)
        layout = QVBoxLayout(self)
        text = QPlainTextEdit(json.dumps(report, indent=2))
        text.setReadOnly(True)
        text.setObjectName("console")
        layout.addWidget(text)


class EvaluateTab(QWidget):
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

        run_box = QGroupBox("Run an evaluation (kev.benchmark)")
        run_form = QVBoxLayout(run_box)

        self.local_radio = QRadioButton("Local checkpoint / trial")
        self.remote_radio = QRadioButton("Running server (--remote)")
        self.local_radio.setChecked(True)
        radios = QHBoxLayout()
        radios.addWidget(self.local_radio)
        radios.addWidget(self.remote_radio)
        radios.addStretch()
        run_form.addLayout(radios)

        self.local_target = PathPicker(mode="dir")
        self.local_target.setText(DEFAULT_RUN)
        self.remote_target = QLineEdit(f"http://127.0.0.1:{DEFAULT_PORT}")
        run_form.addLayout(_row("Local checkpoint/trial path or Hub id:", self.local_target))
        run_form.addLayout(_row("Remote base URL:", self.remote_target))

        self.data = PathPicker(filter_="JSON Lines (*.jsonl)")
        self.out = PathPicker(mode="dir")
        run_form.addLayout(_row("Labelled data (.jsonl):", self.data))
        run_form.addLayout(_row("Output dir:", self.out))

        self.gpu = QSpinBox(); self.gpu.setRange(0, 8); self.gpu.setValue(DEFAULT_GPU)
        self.rotations = QSpinBox(); self.rotations.setRange(1, 16); self.rotations.setValue(1)
        self.allow_test = QCheckBox("Allow scoring the locked test split (--allow-test)")
        self.date_facts = QCheckBox("Apply date-facts preprocessing (--date_facts)")
        run_form.addLayout(_row("GPU index (local checkpoint scoring only):", self.gpu))
        run_form.addLayout(_row("Choice rotations:", self.rotations))
        run_form.addWidget(self.allow_test)
        run_form.addWidget(self.date_facts)

        run_btn = QPushButton("Evaluate")
        run_btn.setObjectName("primary")
        run_btn.clicked.connect(self._run_eval)
        run_form.addWidget(run_btn)
        self.runner = ProcessRunner()
        self.runner.finished.connect(self._on_eval_finished)
        run_form.addWidget(self.runner)
        layout.addWidget(run_box)

        results_box = QGroupBox("Combined results (every evaluate run, every group)")
        results_layout = QVBoxLayout(results_box)
        self.results_table = QTableWidget(0, 8)
        self.results_table.setHorizontalHeaderLabels(["When", "Group", "Target", "N", "Accuracy", "Brier", "ECE", "Coverage @5% err"])
        self.results_table.itemDoubleClicked.connect(self._view_report)
        results_layout.addWidget(self.results_table)
        refresh_results_btn = QPushButton("Refresh")
        refresh_results_btn.clicked.connect(self._refresh_results)
        results_layout.addWidget(refresh_results_btn)
        layout.addWidget(results_box)

        compare_box = QGroupBox("Compare two runs (kev.compare)")
        compare_form = QVBoxLayout(compare_box)
        self.compare_a = QComboBox()
        self.compare_b = QComboBox()
        compare_form.addLayout(_row("Candidate:", self.compare_a))
        compare_form.addLayout(_row("Reference:", self.compare_b))
        compare_note = QLabel(
            "Known upstream limitation: kev.compare crashes (NaN in its \"none of the above\" "
            "diagnostic) when both runs came from a plain --data file rather than Kev's own "
            "--suite -- which is every run this GUI produces. Read the two runs' Combined "
            "Results rows above directly instead of relying on Compare."
        )
        compare_note.setProperty("role", "warn")
        compare_note.setWordWrap(True)
        compare_form.addWidget(compare_note)
        compare_btn = QPushButton("Compare")
        compare_btn.clicked.connect(self._run_compare)
        compare_form.addWidget(compare_btn)
        self.compare_runner = ProcessRunner()
        compare_form.addWidget(self.compare_runner)
        layout.addWidget(compare_box)

        self.group_combo.refresh()
        self.group_combo.currentTextChanged.connect(self._on_group_changed)
        self._on_group_changed(self.group_combo.currentText())
        self._refresh_results()

    def _on_group_changed(self, group: str) -> None:
        if not group:
            return
        stamp = time.strftime("%Y%m%d-%H%M%S")
        sync_auto_path(self.out, self._auto, "out", str(GROUPS_ROOT / group / "eval" / stamp))

    def _run_eval(self) -> None:
        group = self.group_combo.currentText()
        if not self.data.text() or not self.out.text():
            self.runner.append("[pick a data file and an output dir first]\n")
            return
        args = [KEV_VENV_PY, "-m", "kev.benchmark", "--data", self.data.text(), "--out", self.out.text(),
                "--device", "cuda", "--rotations", str(self.rotations.value())]
        if self.local_radio.isChecked():
            target = self.local_target.text().strip()
            args += ["--run", target]
        else:
            target = self.remote_target.text().strip()
            args += ["--remote", target]
        if self.allow_test.isChecked():
            args.append("--allow-test")
        if self.date_facts.isChecked():
            args.append("--date_facts")
        self._pending = {"group": group, "target": target, "data": self.data.text(), "out_dir": self.out.text()}
        env = {**OFFLINE_ENV, "CUDA_VISIBLE_DEVICES": str(self.gpu.value())}
        if self.local_radio.isChecked():
            # kev.benchmark's own default (LoadOptions.from_env with KEV_DTYPE unset) is fp32
            # unless the checkpoint's own head.pt recorded otherwise -- ~36GB for a 9B model,
            # which doesn't fit the P40. kev.serve sidesteps this by hardcoding bf16 itself;
            # do the same here so scoring the plain released checkpoint doesn't OOM.
            env["KEV_DTYPE"] = "bf16"
        self.runner.run(args, cwd=KEV_ROOT, env_overrides=env)

    def _on_eval_finished(self, code: int) -> None:
        if code != 0 or not hasattr(self, "_pending"):
            return
        entry = results_store.add_entry(**self._pending)
        if entry:
            self.runner.append("\n[recorded in combined results below]\n")
            self._refresh_results()

    def _refresh_results(self) -> None:
        entries = results_store.load()
        self.results_table.setRowCount(len(entries))
        self.compare_a.clear()
        self.compare_b.clear()
        for r, e in enumerate(entries):
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(e["timestamp"]))
            self.results_table.setItem(r, 0, QTableWidgetItem(when))
            self.results_table.setItem(r, 1, QTableWidgetItem(e["group"]))
            self.results_table.setItem(r, 2, QTableWidgetItem(e["target"]))
            self.results_table.setItem(r, 3, QTableWidgetItem(str(e["n"])))
            self.results_table.setItem(r, 4, QTableWidgetItem(f"{e['accuracy']:.4f}" if e["accuracy"] is not None else "?"))
            self.results_table.setItem(r, 5, QTableWidgetItem(f"{e['brier']:.4f}" if e["brier"] is not None else "?"))
            self.results_table.setItem(r, 6, QTableWidgetItem(f"{e['ece']:.4f}" if e["ece"] is not None else "?"))
            cov = e.get("coverage_at_5pct_error")
            self.results_table.setItem(r, 7, QTableWidgetItem(f"{cov:.4f}" if cov is not None else "?"))
            item = self.results_table.item(r, 0)
            item.setData(1000, e["out_dir"])
            label = f"{when} · {e['group']} · {e['target']}"
            self.compare_a.addItem(label, e["out_dir"])
            self.compare_b.addItem(label, e["out_dir"])

    def _view_report(self, item: QTableWidgetItem) -> None:
        out_dir = self.results_table.item(item.row(), 0).data(1000)
        report_path = Path(out_dir) / "report.json"
        if not report_path.exists():
            return
        ReportDialog(json.loads(report_path.read_text()), self).exec()

    def _run_compare(self) -> None:
        candidate, reference = self.compare_a.currentData(), self.compare_b.currentData()
        if not candidate or not reference:
            self.compare_runner.append("[need at least two evaluate runs in the ledger first]\n")
            return
        out = Path(candidate) / "compare"
        args = [KEV_VENV_PY, "-m", "kev.compare", "--candidate", candidate, "--reference", reference, "--out", str(out)]
        self.compare_runner.run(args, cwd=KEV_ROOT, env_overrides=OFFLINE_ENV)
