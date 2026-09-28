"""Tree-style tracker: groups -> registered source folders (scanned recursively, live) ->
discovered files -> stage into the group's isolated data/ directory."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

import kev_ipc
from paths import DATA_EXTENSIONS, GROUPS_ROOT, KEVCTL, KEV_ROOT, KEV_VENV_PY, SOURCES_FILE

GROUP_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _load_sources() -> dict:
    if SOURCES_FILE.exists():
        try:
            return json.loads(SOURCES_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_sources(sources: dict) -> None:
    SOURCES_FILE.write_text(json.dumps(sources, indent=2))


class GroupsTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sources = _load_sources()

        layout = QVBoxLayout(self)
        info = QLabel(
            "Groups isolate private data: a source folder registered under one group is never scanned "
            "into another, and staging always goes through kevctl's cross-group refusal check."
        )
        info.setProperty("role", "dim")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Group / Source / File", "Details"])
        self.tree.setColumnWidth(0, 420)
        layout.addWidget(self.tree)

        buttons = QHBoxLayout()
        new_group_btn = QPushButton("New Group")
        new_group_btn.clicked.connect(self._new_group)
        include_btn = QPushButton("Include Folder…")
        include_btn.clicked.connect(self._include_folder)
        remove_source_btn = QPushButton("Remove Source")
        remove_source_btn.clicked.connect(self._remove_source)
        stage_btn = QPushButton("Stage Selected File(s)")
        stage_btn.setObjectName("primary")
        stage_btn.clicked.connect(self._stage_selected)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        buttons.addWidget(new_group_btn)
        buttons.addWidget(include_btn)
        buttons.addWidget(remove_source_btn)
        buttons.addStretch()
        buttons.addWidget(stage_btn)
        buttons.addWidget(refresh_btn)
        layout.addLayout(buttons)

        self.refresh()

    # ---------- actions ----------

    def _new_group(self) -> None:
        name, ok = QInputDialog.getText(self, "New group", "Group name (letters/digits/-/_ only):")
        if not ok or not name:
            return
        if not GROUP_NAME_RE.fullmatch(name):
            QMessageBox.warning(self, "Invalid name", "Group names may only use letters, digits, - and _.")
            return
        d = GROUPS_ROOT / name
        (d / "data").mkdir(parents=True, exist_ok=True)
        (d / "trials").mkdir(parents=True, exist_ok=True)
        self.sources.setdefault(name, [])
        _save_sources(self.sources)
        self.refresh()

    def _include_folder(self) -> None:
        item = self.tree.currentItem()
        group = self._group_of(item)
        if not group:
            QMessageBox.information(self, "Pick a group", "Select a group (or one of its rows) first.")
            return
        folder = QFileDialog.getExistingDirectory(self, f"Include a folder for group '{group}'", str(Path.home()))
        if not folder:
            return
        self.sources.setdefault(group, [])
        if folder not in self.sources[group]:
            self.sources[group].append(folder)
            _save_sources(self.sources)
        self.refresh()

    def _remove_source(self) -> None:
        item = self.tree.currentItem()
        data = item.data(0, Qt.UserRole) if item else None
        if not data or data.get("kind") != "source":
            QMessageBox.information(self, "Pick a source", "Select a registered source folder row to remove it.")
            return
        group, folder = data["group"], data["path"]
        self.sources.get(group, []).remove(folder)
        _save_sources(self.sources)
        self.refresh()

    def _stage_selected(self) -> None:
        staged, errors = [], []
        for item in self.tree.selectedItems():
            data = item.data(0, Qt.UserRole)
            if not data or data.get("kind") != "file":
                continue
            try:
                dest = kev_ipc.stage_file(data["group"], data["path"])
                staged.append(dest)
            except RuntimeError as e:
                errors.append(f"{data['path']}: {e}")
        if staged:
            QMessageBox.information(self, "Staged", "\n".join(staged))
        if errors:
            QMessageBox.warning(self, "Some files were refused", "\n".join(errors))
        if staged:
            self.refresh()

    def _group_of(self, item: QTreeWidgetItem | None) -> str | None:
        while item is not None:
            data = item.data(0, Qt.UserRole)
            if data and data.get("kind") == "group":
                return data["group"]
            if data and "group" in data:
                return data["group"]
            item = item.parent()
        return None

    # ---------- rendering ----------

    def refresh(self) -> None:
        try:
            groups_info = {g["group"]: g for g in kev_ipc.list_groups()}
        except RuntimeError:
            groups_info = {}
        for name in list(self.sources):
            groups_info.setdefault(name, {"group": name, "data_files": [], "trials": []})

        self.tree.clear()
        for name in sorted(groups_info):
            g = groups_info[name]
            group_item = QTreeWidgetItem([name, f"{len(g['data_files'])} staged file(s), {len(g['trials'])} trial(s)"])
            group_item.setData(0, Qt.UserRole, {"kind": "group", "group": name})
            self.tree.addTopLevelItem(group_item)

            staged_item = QTreeWidgetItem(["Staged data", ""])
            staged_item.setData(0, Qt.UserRole, {"kind": "staged", "group": name})
            for f in sorted(g["data_files"]):
                fi = QTreeWidgetItem([Path(f).name, f])
                fi.setData(0, Qt.UserRole, {"kind": "staged_file", "group": name, "path": f})
                staged_item.addChild(fi)
            group_item.addChild(staged_item)

            for folder in self.sources.get(name, []):
                source_item = QTreeWidgetItem([folder, "registered source"])
                source_item.setData(0, Qt.UserRole, {"kind": "source", "group": name, "path": folder})
                group_item.addChild(source_item)
                for f in self._scan(folder):
                    fi = QTreeWidgetItem([Path(f).name, f])
                    fi.setData(0, Qt.UserRole, {"kind": "file", "group": name, "path": f})
                    source_item.addChild(fi)
        self.tree.expandToDepth(0)

    @staticmethod
    def _scan(folder: str, limit: int = 500, max_visited: int = 50_000) -> list[str]:
        """Recursive scan, bounded two ways: `limit` matches found, `max_visited` entries
        examined. Without the second bound, a folder with zero matching files (e.g. a huge
        node_modules) would walk its entire tree with no early exit, freezing the UI --
        this runs synchronously on the GUI thread on every refresh()."""
        root = Path(folder)
        if not root.is_dir():
            return []
        found = []
        for visited, p in enumerate(root.rglob("*"), start=1):
            if visited > max_visited:
                break
            if p.is_file() and p.suffix.lower() in DATA_EXTENSIONS:
                found.append(str(p))
                if len(found) >= limit:
                    break
        return sorted(found)
