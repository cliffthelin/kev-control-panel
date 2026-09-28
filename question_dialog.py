"""Add/Edit dialog for one question in a workload spec (data-format.md's `criteria` shape)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

TYPES = ["choice", "noul", "score"]


class _ChoiceEditor(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Option name", "Description (optional)"])
        layout.addWidget(self.table)
        row_btns = QHBoxLayout()
        add_btn, remove_btn = QPushButton("Add option"), QPushButton("Remove selected")
        add_btn.clicked.connect(lambda: self._add_row())
        remove_btn.clicked.connect(self._remove_row)
        row_btns.addWidget(add_btn)
        row_btns.addWidget(remove_btn)
        layout.addLayout(row_btns)

    def _add_row(self, name: str = "", desc: str = "") -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(name))
        self.table.setItem(r, 1, QTableWidgetItem(desc))

    def _remove_row(self) -> None:
        for r in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(r)

    def set_criteria(self, criteria: dict) -> None:
        self.table.setRowCount(0)
        for name, desc in (criteria or {}).items():
            self._add_row(name, desc or "")

    def names(self) -> list[str]:
        out = []
        for r in range(self.table.rowCount()):
            name_item = self.table.item(r, 0)
            if name_item and name_item.text().strip():
                out.append(name_item.text().strip())
        return out

    def get_criteria(self) -> dict:
        # A duplicate name silently collapses here (dict keys); callers must check names()
        # for duplicates BEFORE calling this if they want to warn instead of losing a row.
        out = {}
        for r in range(self.table.rowCount()):
            name_item = self.table.item(r, 0)
            if not name_item or not name_item.text().strip():
                continue
            desc_item = self.table.item(r, 1)
            out[name_item.text().strip()] = (desc_item.text().strip() if desc_item and desc_item.text().strip() else None)
        return out


class _ScoreEditor(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Levels, low to high:"))
        self.list = QListWidget()
        layout.addWidget(self.list)
        btns = QHBoxLayout()
        add_btn, remove_btn = QPushButton("Add level"), QPushButton("Remove selected")
        up_btn, down_btn = QPushButton("Move up"), QPushButton("Move down")
        add_btn.clicked.connect(lambda: self._add_item(""))
        remove_btn.clicked.connect(self._remove_item)
        up_btn.clicked.connect(lambda: self._move(-1))
        down_btn.clicked.connect(lambda: self._move(1))
        for b in (add_btn, remove_btn, up_btn, down_btn):
            btns.addWidget(b)
        layout.addLayout(btns)

    def _add_item(self, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.list.addItem(item)

    def _remove_item(self) -> None:
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))

    def _move(self, delta: int) -> None:
        row = self.list.currentRow()
        new_row = row + delta
        if row < 0 or not (0 <= new_row < self.list.count()):
            return
        item = self.list.takeItem(row)
        self.list.insertItem(new_row, item)
        self.list.setCurrentRow(new_row)

    def set_levels(self, levels: list) -> None:
        self.list.clear()
        for text in levels or []:
            self._add_item(text)

    def get_levels(self) -> list:
        return [self.list.item(i).text().strip() for i in range(self.list.count()) if self.list.item(i).text().strip()]


class _NoulEditor(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        self.true_edit = QLineEdit()
        self.false_edit = QLineEdit()
        form.addRow("True means (optional):", self.true_edit)
        form.addRow("False means (optional):", self.false_edit)

    def set_criteria(self, criteria: dict | None) -> None:
        criteria = criteria or {}
        self.true_edit.setText(str(criteria.get("true", "") or ""))
        self.false_edit.setText(str(criteria.get("false", "") or ""))

    def get_criteria(self) -> dict | None:
        t, f = self.true_edit.text().strip(), self.false_edit.text().strip()
        return {"true": t, "false": f} if (t or f) else None


class QuestionDialog(QDialog):
    """Returns a (question_id, question_dict) pair via `result_question()` after exec()."""

    def __init__(self, question_id: str = "", question: dict | None = None, existing_ids: set | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Question")
        self.existing_ids = existing_ids or set()
        self._editing_id = question_id

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.id_edit = QLineEdit(question_id)
        self.type_combo = QComboBox()
        self.type_combo.addItems(TYPES)
        self.instructions_edit = QPlainTextEdit()
        self.instructions_edit.setFixedHeight(60)
        form.addRow("id:", self.id_edit)
        form.addRow("type:", self.type_combo)
        form.addRow("instructions:", self.instructions_edit)
        layout.addLayout(form)

        self.stack = QStackedWidget()
        self.choice_editor = _ChoiceEditor()
        self.noul_editor = _NoulEditor()
        self.score_editor = _ScoreEditor()
        self.stack.addWidget(self.choice_editor)
        self.stack.addWidget(self.noul_editor)
        self.stack.addWidget(self.score_editor)
        layout.addWidget(self.stack)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if question:
            self.type_combo.setCurrentText(question.get("type", "choice"))
            self.instructions_edit.setPlainText(question.get("instructions", ""))
            self.choice_editor.set_criteria(question.get("criteria") if question.get("type") == "choice" else {})
            self.noul_editor.set_criteria(question.get("criteria") if question.get("type") == "noul" else {})
            self.score_editor.set_levels(question.get("criteria") if question.get("type") == "score" else [])
        self._on_type_changed(self.type_combo.currentText())
        self._question: tuple | None = None

    def _on_type_changed(self, type_name: str) -> None:
        self.stack.setCurrentIndex(TYPES.index(type_name))

    def _on_accept(self) -> None:
        qid = self.id_edit.text().strip()
        if not qid:
            QMessageBox.warning(self, "Missing id", "Give this question an id.")
            return
        if qid != self._editing_id and qid in self.existing_ids:
            QMessageBox.warning(self, "Duplicate id", f"Question id {qid!r} already exists.")
            return
        instructions = self.instructions_edit.toPlainText().strip()
        if not instructions:
            QMessageBox.warning(self, "Missing instructions", "Write the question text.")
            return
        type_name = self.type_combo.currentText()
        if type_name == "choice":
            names = self.choice_editor.names()
            if len(names) != len(set(names)):
                dupes = sorted({n for n in names if names.count(n) > 1})
                QMessageBox.warning(self, "Duplicate option name", f"Option name(s) repeated, would silently collapse: {', '.join(dupes)}")
                return
            criteria = self.choice_editor.get_criteria()
            if len(criteria) < 2:
                QMessageBox.warning(self, "Not enough options", "A choice question needs at least 2 options.")
                return
        elif type_name == "score":
            criteria = self.score_editor.get_levels()
            if len(criteria) < 2:
                QMessageBox.warning(self, "Not enough levels", "A score question needs at least 2 ordered levels.")
                return
        else:
            criteria = self.noul_editor.get_criteria()
        question = {"type": type_name, "instructions": instructions}
        if criteria:
            question["criteria"] = criteria
        self._question = (qid, question)
        self.accept()

    def result_question(self) -> tuple | None:
        return self._question
