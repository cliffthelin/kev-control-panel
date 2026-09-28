"""Small reusable widgets shared across tabs."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget

import kev_ipc


class PathPicker(QWidget):
    """A line edit plus a Browse... button, for a file/dir/save-path field."""

    def __init__(self, mode: str = "file", filter_: str = "", start_dir: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mode = mode
        self.filter = filter_
        self.start_dir = start_dir or str(Path.home())
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        layout.addWidget(self.edit)
        layout.addWidget(browse)

    def _browse(self) -> None:
        base = self.edit.text().strip() or self.start_dir
        if self.mode == "dir":
            path = QFileDialog.getExistingDirectory(self, "Select folder", base)
        elif self.mode == "save":
            path, _ = QFileDialog.getSaveFileName(self, "Save as", base, self.filter)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select file", base, self.filter)
        if path:
            self.edit.setText(path)

    def text(self) -> str:
        return self.edit.text().strip()

    def setText(self, value: str) -> None:
        self.edit.setText(value)


def sync_auto_path(picker: "PathPicker", tracker: dict, key: str, new_value: str) -> None:
    """Update `picker` to `new_value` unless the user has edited it away from the value this
    helper last auto-set for `key`. Without this, switching groups leaves a field silently
    pointed at the PREVIOUS group's path -- exactly the cross-group mismatch this project
    otherwise goes out of its way to prevent."""
    current = picker.text()
    if not current or current == tracker.get(key):
        picker.setText(new_value)
    tracker[key] = new_value


class GroupCombo(QComboBox):
    """A combo box of group names, refreshed from kevctl."""

    def refresh(self, keep: str | None = None) -> list[dict]:
        keep = keep if keep is not None else self.currentText()
        try:
            info = kev_ipc.list_groups()
        except RuntimeError:
            info = []
        self.blockSignals(True)
        self.clear()
        for g in info:
            self.addItem(g["group"])
        idx = self.findText(keep)
        if idx >= 0:
            self.setCurrentIndex(idx)
        self.blockSignals(False)
        return info
