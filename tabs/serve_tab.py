"""Wraps `kevctl start/stop/restart`, a live status+GPU dashboard, and a quick-test panel
that POSTs straight to the running server's /v1/systemone."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

import kev_ipc
from paths import DEFAULT_GPU, DEFAULT_PORT, DEFAULT_RUN, KEVCTL, KEV_ROOT, KEV_VENV_PY
from runner import ProcessRunner
from widgets import PathPicker


def _row(label, widget):
    r = QHBoxLayout()
    r.addWidget(QLabel(label))
    r.addWidget(widget)
    return r


class ServeTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        control_box = QGroupBox("Server")
        control = QVBoxLayout(control_box)
        self.run_field = QLineEdit(DEFAULT_RUN)
        self.run_field.setPlaceholderText("Hub id, or a local trial path (browse below)")
        browse_btn = QPushButton("Browse trial…")
        browse_btn.clicked.connect(self._browse_run)
        run_row = QHBoxLayout()
        run_row.addWidget(QLabel("Run:"))
        run_row.addWidget(self.run_field)
        run_row.addWidget(browse_btn)
        control.addLayout(run_row)

        self.port = QSpinBox(); self.port.setRange(1, 65535); self.port.setValue(DEFAULT_PORT)
        self.gpu = QSpinBox(); self.gpu.setRange(0, 8); self.gpu.setValue(DEFAULT_GPU)
        control.addLayout(_row("Port:", self.port))
        control.addLayout(_row("GPU index:", self.gpu))

        btn_row = QHBoxLayout()
        start_btn = QPushButton("Start")
        start_btn.setObjectName("primary")
        start_btn.clicked.connect(self._start)
        stop_btn = QPushButton("Stop")
        stop_btn.setObjectName("danger")
        stop_btn.clicked.connect(self._stop)
        restart_btn = QPushButton("Restart")
        restart_btn.clicked.connect(self._restart)
        btn_row.addWidget(start_btn)
        btn_row.addWidget(stop_btn)
        btn_row.addWidget(restart_btn)
        control.addLayout(btn_row)

        self.runner = ProcessRunner()
        control.addWidget(self.runner)
        layout.addWidget(control_box)

        dash_box = QGroupBox("Live status")
        dash = QVBoxLayout(dash_box)
        self.status_label = QLabel("checking…")
        self.status_label.setProperty("role", "dim")
        dash.addWidget(self.status_label)
        self.gpu_table = QTableWidget(0, 6)
        self.gpu_table.setHorizontalHeaderLabels(["GPU", "Name", "Temp", "Util", "Memory", "Power"])
        dash.addWidget(self.gpu_table)
        layout.addWidget(dash_box)

        test_box = QGroupBox("Quick test (POST /v1/systemone)")
        test = QVBoxLayout(test_box)
        self.test_body = QPlainTextEdit(json.dumps({
            "state": "Shoes arrived two weeks late and in the wrong size.",
            "model": "kev-latest",
            "questions": {"escalate": {"type": "noul", "instructions": "Does this need urgent attention?"}},
        }, indent=2))
        self.test_body.setFixedHeight(140)
        test.addWidget(self.test_body)
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self._send_test)
        test.addWidget(send_btn)
        self.test_result = QPlainTextEdit()
        self.test_result.setObjectName("console")
        self.test_result.setReadOnly(True)
        self.test_result.setFixedHeight(120)
        test.addWidget(self.test_result)
        layout.addWidget(test_box)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(2000)
        self._poll()

    def _browse_run(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        from paths import GROUPS_ROOT
        path = QFileDialog.getExistingDirectory(self, "Select a trial directory", str(GROUPS_ROOT))
        if path:
            self.run_field.setText(path)

    def _start(self) -> None:
        args = [KEV_VENV_PY, KEVCTL, "start", "--run", self.run_field.text().strip(),
                "--port", str(self.port.value()), "--gpu", str(self.gpu.value())]
        self.runner.run(args, cwd=KEV_ROOT)

    def _stop(self) -> None:
        # force=True: Stop must always win, even if Start/Restart is still mid-poll
        # (first-run model download/load can take a while and would otherwise block it).
        self.runner.run([KEV_VENV_PY, KEVCTL, "stop"], cwd=KEV_ROOT, force=True)

    def _restart(self) -> None:
        args = [KEV_VENV_PY, KEVCTL, "restart", "--run", self.run_field.text().strip(),
                "--port", str(self.port.value()), "--gpu", str(self.gpu.value())]
        self.runner.run(args, cwd=KEV_ROOT)

    def _poll(self) -> None:
        try:
            status = kev_ipc.server_status()
        except RuntimeError as e:
            self.status_label.setText(f"status check failed: {e}")
            return
        server = status["server"]
        if server.get("running"):
            meta = server.get("meta") or {}
            healthy = "healthy" if server.get("healthy") else ("starting…" if server.get("port_open") else "not responding")
            self.status_label.setText(
                f"running  pid {server['pid']}  uptime {server['uptime']}  "
                f"model {meta.get('run')}  port {meta.get('port')}  gpu {meta.get('gpu')}  [{healthy}]"
            )
            self.status_label.setProperty("role", "ok")
        else:
            self.status_label.setText("stopped")
            self.status_label.setProperty("role", "dim")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

        gpus = status.get("gpus", [])
        self.gpu_table.setRowCount(len(gpus))
        active_gpu = (server.get("meta") or {}).get("gpu") if server.get("running") else None
        for r, g in enumerate(gpus):
            marker = "▶ " if active_gpu == g["index"] else ""
            self.gpu_table.setItem(r, 0, QTableWidgetItem(f"{marker}{g['index']}"))
            self.gpu_table.setItem(r, 1, QTableWidgetItem(g["name"]))
            self.gpu_table.setItem(r, 2, QTableWidgetItem(f"{g['temp']}°C"))
            self.gpu_table.setItem(r, 3, QTableWidgetItem(f"{g['util_gpu']}%"))
            self.gpu_table.setItem(r, 4, QTableWidgetItem(f"{g['mem_used']} / {g['mem_total']} MiB"))
            self.gpu_table.setItem(r, 5, QTableWidgetItem(f"{g['pwr']} / {g['pwr_limit']} W"))

    def _send_test(self) -> None:
        try:
            body = self.test_body.toPlainText().encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.port.value()}/v1/systemone", data=body,
                headers={"content-type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
            self.test_result.setPlainText(json.dumps(result, indent=2))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            self.test_result.setPlainText(f"request failed: {e}")
