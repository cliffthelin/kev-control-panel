"""Reusable subprocess runner: launches a command, streams merged stdout/stderr into a
console widget, and reports the exit code. Used by every tab that wraps a script/CLI so
none of them re-implement process handling."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from paths import KEV_ROOT


class _ProcessThread(QThread):
    output = Signal(str)
    finished_code = Signal(int)

    def __init__(self, argv: list, cwd: Path | str, env: dict) -> None:
        super().__init__()
        self.argv = [str(a) for a in argv]
        self.cwd = str(cwd)
        self.env = env
        self._proc: subprocess.Popen | None = None

    def run(self) -> None:
        try:
            self._proc = subprocess.Popen(
                self.argv, cwd=self.cwd, env=self.env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, errors="replace",   # a stray non-UTF8 byte must not crash the thread
            )
        except OSError as e:
            self.output.emit(f"failed to launch: {e}\n")
            self.finished_code.emit(-1)
            return
        for line in self._proc.stdout:
            self.output.emit(line)
        self.finished_code.emit(self._proc.wait())

    def request_stop(self) -> None:
        """Non-blocking: send SIGTERM and return immediately. Never call proc.wait() here --
        this runs on whichever thread calls it, typically the GUI thread via a button click,
        and blocking it freezes the whole window."""
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def kill_now(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.kill()


class ProcessRunner(QWidget):
    """A status line + Stop button + scrollback console, plus `run()`/`finished` for callers."""

    finished = Signal(int)
    _ESCALATE_MS = 4000   # grace period before a non-cooperating process gets SIGKILL

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._thread: _ProcessThread | None = None
        # Threads being stopped during a force-restart, kept referenced until they actually
        # finish: a QThread garbage-collected while Qt still considers it running aborts the
        # process, so `self._thread` being reassigned must never drop the last reference.
        self._retiring: list[_ProcessThread] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        self.status_label = QLabel("idle")
        self.status_label.setProperty("role", "dim")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(lambda: self.console.clear())
        header.addWidget(self.status_label)
        header.addStretch()
        header.addWidget(self.clear_btn)
        header.addWidget(self.stop_btn)
        layout.addLayout(header)

        self.console = QPlainTextEdit()
        self.console.setObjectName("console")
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(20000)
        layout.addWidget(self.console)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def run(self, argv: list, cwd: Path | str = KEV_ROOT, env_overrides: dict | None = None, force: bool = False) -> None:
        if self.is_running():
            if not force:
                self.append("[a run is already in progress in this panel]\n")
                return
            self.append("[interrupting the current run to start a new one]\n")
            self._retire(self._thread)
            self._thread = None

        env = os.environ.copy()
        if env_overrides:
            env.update(env_overrides)
        self.console.clear()
        self.append(f"$ {' '.join(str(a) for a in argv)}\n\n")
        self.status_label.setText("running…")
        self.status_label.setProperty("role", "accent")
        self._restyle_status()
        self.stop_btn.setEnabled(True)

        self._thread = _ProcessThread(argv, cwd, env)
        self._thread.output.connect(self.append)
        self._thread.finished_code.connect(self._on_finished)
        self._thread.start()

    def append(self, text: str) -> None:
        text = text.replace("\r", "\n")
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.console.setTextCursor(cursor)
        self.console.insertPlainText(text)
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    def _on_finished(self, code: int) -> None:
        ok = code == 0
        self.status_label.setText(f"exit {code}" if code >= 0 else "failed to launch")
        self.status_label.setProperty("role", "ok" if ok else "bad")
        self._restyle_status()
        self.stop_btn.setEnabled(False)
        self.finished.emit(code)

    def _restyle_status(self) -> None:
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def stop(self) -> None:
        """The Stop button: non-blocking, escalates to SIGKILL after a grace period if the
        process doesn't exit on its own."""
        if self._thread:
            self._escalate_later(self._thread)

    def _retire(self, thread: _ProcessThread) -> None:
        self._retiring.append(thread)
        thread.finished_code.connect(lambda _code, t=thread: self._drop_retiring(t))
        self._escalate_later(thread)

    def _drop_retiring(self, thread: _ProcessThread) -> None:
        if thread in self._retiring:
            self._retiring.remove(thread)

    def _escalate_later(self, thread: _ProcessThread) -> None:
        thread.request_stop()
        QTimer.singleShot(self._ESCALATE_MS, lambda: thread.kill_now() if thread.isRunning() else None)

    def shutdown(self) -> None:
        """Stop and synchronously join every live thread (current + any still retiring).
        Call before the app quits -- destroying a still-running QThread crashes the process."""
        threads = list(self._retiring)
        if self._thread is not None and self._thread not in threads:
            threads.append(self._thread)
        for t in threads:
            if t.isRunning():
                t.request_stop()
        for t in threads:
            if t.isRunning() and not t.wait(3000):
                t.kill_now()
                t.wait(2000)
