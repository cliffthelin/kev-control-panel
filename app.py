#!/usr/bin/env python3
"""Kev control panel: a local-only GUI over the whole fine-tuning workflow --
groups/data tracking, question building, import/generate/validate, train, serve, evaluate.

Run: ~/kev/gui/.venv/bin/python ~/kev/gui/app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

import theme
from runner import ProcessRunner
from tabs.evaluate_tab import EvaluateTab
from tabs.generate_tab import GenerateTab
from tabs.groups_tab import GroupsTab
from tabs.import_tab import ImportTab
from tabs.serve_tab import ServeTab
from tabs.train_tab import TrainTab
from tabs.validate_tab import ValidateTab
from tabs.workload_tab import WorkloadTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Kev Control Panel")
        self.resize(1180, 860)

        tabs = QTabWidget()
        tabs.addTab(GroupsTab(), "Groups")
        tabs.addTab(WorkloadTab(), "Questions")
        tabs.addTab(ImportTab(), "Import")
        tabs.addTab(GenerateTab(), "Generate")
        tabs.addTab(ValidateTab(), "Validate")
        tabs.addTab(TrainTab(), "Train")
        tabs.addTab(ServeTab(), "Serve")
        tabs.addTab(EvaluateTab(), "Evaluate")
        self.setCentralWidget(tabs)

    def closeEvent(self, event) -> None:
        # A ProcessRunner's subprocess thread destroyed while still running crashes the
        # process (Qt aborts, not a catchable Python exception) -- always join first,
        # whether the user is mid-train, mid-start, or mid-generate.
        for runner in self.findChildren(ProcessRunner):
            runner.shutdown()
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    theme.apply(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
