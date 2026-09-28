"""CRUD editor for a group's workload.json -- the question/spec definition consumed by
generate_data.py, convert_data.py and plan_size.py."""
from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QAbstractItemView, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from paths import ASSETS, GROUPS_ROOT
from question_dialog import QuestionDialog
from widgets import GroupCombo


class WorkloadTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.questions: dict[str, dict] = {}

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Group:"))
        self.group_combo = GroupCombo()
        self.group_combo.currentTextChanged.connect(self._load)
        top.addWidget(self.group_combo)
        refresh_btn = QPushButton("Refresh groups")
        refresh_btn.clicked.connect(lambda: self.group_combo.refresh())
        top.addWidget(refresh_btn)
        template_btn = QPushButton("Load example template")
        template_btn.clicked.connect(self._load_template)
        top.addWidget(template_btn)
        top.addStretch()
        layout.addLayout(top)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.domain_edit = QPlainTextEdit()
        self.domain_edit.setFixedHeight(50)
        self.state_edit = QPlainTextEdit()
        self.state_edit.setFixedHeight(50)
        self.guidance_edit = QPlainTextEdit()
        self.guidance_edit.setFixedHeight(70)
        self.variety_edit = QPlainTextEdit()
        self.variety_edit.setFixedHeight(60)
        self.variety_edit.setPlaceholderText("One variety axis per line, e.g.\ntone: polite, sarcastic, furious")
        form.addRow("name:", self.name_edit)
        form.addRow("domain:", self.domain_edit)
        form.addRow("state (description):", self.state_edit)
        form.addRow("guidance:", self.guidance_edit)
        form.addRow("variety:", self.variety_edit)
        layout.addLayout(form)

        layout.addWidget(QLabel("Questions:"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["id", "type", "instructions"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemDoubleClicked.connect(lambda _: self._edit_question())
        layout.addWidget(self.table)

        q_buttons = QHBoxLayout()
        add_btn, edit_btn, del_btn = QPushButton("Add question"), QPushButton("Edit"), QPushButton("Delete")
        add_btn.clicked.connect(self._add_question)
        edit_btn.clicked.connect(self._edit_question)
        del_btn.clicked.connect(self._delete_question)
        q_buttons.addWidget(add_btn)
        q_buttons.addWidget(edit_btn)
        q_buttons.addWidget(del_btn)
        q_buttons.addStretch()
        layout.addLayout(q_buttons)

        save_row = QHBoxLayout()
        save_btn = QPushButton("Save workload.json")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        self.status_label = QLabel("")
        self.status_label.setProperty("role", "dim")
        save_row.addWidget(save_btn)
        save_row.addWidget(self.status_label)
        save_row.addStretch()
        layout.addLayout(save_row)

        self.group_combo.refresh()
        self._load(self.group_combo.currentText())

    # ---------- data plumbing ----------

    def _workload_path(self):
        group = self.group_combo.currentText()
        if not group:
            return None
        d = GROUPS_ROOT / group
        d.mkdir(parents=True, exist_ok=True)
        return d / "workload.json"

    def _load(self, _group: str) -> None:
        path = self._workload_path()
        self.questions = {}
        if path and path.exists():
            try:
                spec = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                QMessageBox.warning(self, "Could not read workload.json", str(e))
                spec = {}
            self._populate(spec)
            self.status_label.setText(f"loaded {path}")
        else:
            self._populate({})
            self.status_label.setText("no workload.json yet for this group" if path else "pick a group first")

    def _load_template(self) -> None:
        example = ASSETS / "workload.example.json"
        if not example.exists():
            QMessageBox.warning(self, "Missing template", str(example))
            return
        self._populate(json.loads(example.read_text()))
        self.status_label.setText("loaded example template -- edit and Save to write it for this group")

    def _populate(self, spec: dict) -> None:
        self.name_edit.setText(spec.get("name", ""))
        self.domain_edit.setPlainText(spec.get("domain", ""))
        self.state_edit.setPlainText(spec.get("state", ""))
        self.guidance_edit.setPlainText(spec.get("guidance", ""))
        self.variety_edit.setPlainText("\n".join(spec.get("variety", [])))
        self.questions = dict(spec.get("questions", {}))
        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        for qid, q in self.questions.items():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(qid))
            self.table.setItem(r, 1, QTableWidgetItem(q.get("type", "")))
            self.table.setItem(r, 2, QTableWidgetItem(q.get("instructions", "")))

    def _selected_qid(self) -> str | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        return self.table.item(rows[0].row(), 0).text()

    # ---------- question CRUD ----------

    def _add_question(self) -> None:
        dialog = QuestionDialog(existing_ids=set(self.questions), parent=self)
        if dialog.exec():
            qid, question = dialog.result_question()
            self.questions[qid] = question
            self._refresh_table()

    def _edit_question(self) -> None:
        qid = self._selected_qid()
        if not qid:
            return
        dialog = QuestionDialog(qid, self.questions[qid], existing_ids=set(self.questions) - {qid}, parent=self)
        if dialog.exec():
            new_qid, question = dialog.result_question()
            if new_qid != qid:
                del self.questions[qid]
            self.questions[new_qid] = question
            self._refresh_table()

    def _delete_question(self) -> None:
        qid = self._selected_qid()
        if not qid:
            return
        if QMessageBox.question(self, "Delete question", f"Delete {qid!r}?") == QMessageBox.Yes:
            del self.questions[qid]
            self._refresh_table()

    # ---------- save ----------

    def _save(self) -> None:
        path = self._workload_path()
        if not path:
            QMessageBox.warning(self, "No group selected", "Pick or create a group first (Groups tab).")
            return
        if not self.questions:
            QMessageBox.warning(self, "No questions", "Add at least one question first.")
            return
        spec = {
            "name": self.name_edit.text().strip() or path.parent.name,
            "domain": self.domain_edit.toPlainText().strip(),
            "state": self.state_edit.toPlainText().strip(),
            "questions": self.questions,
        }
        guidance = self.guidance_edit.toPlainText().strip()
        if guidance:
            spec["guidance"] = guidance
        variety = [line.strip() for line in self.variety_edit.toPlainText().splitlines() if line.strip()]
        if variety:
            spec["variety"] = variety
        path.write_text(json.dumps(spec, indent=2))
        self.status_label.setText(f"saved {path}")
