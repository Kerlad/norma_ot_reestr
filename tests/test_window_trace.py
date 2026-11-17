"""Startup flash diagnostics (NORMAOT_TRACE_WINDOWS): off by default, logs shown windows without texts."""
import logging

from PySide6.QtWidgets import QApplication, QLabel

from utils import window_trace

_app = QApplication.instance() or QApplication([])


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv(window_trace.ENV_VAR, raising=False)
    assert window_trace.install(_app) is False


def test_logs_parentless_window_without_its_text(monkeypatch, caplog):
    monkeypatch.setenv(window_trace.ENV_VAR, "1")
    tracer = window_trace.WindowTracer()
    _app.installEventFilter(tracer)
    try:
        with caplog.at_level(logging.INFO, logger="window_trace"):
            w = QLabel("Иванов Иван 112-233-445 95")
            w.show()
            w.hide()
            _app.processEvents()
    finally:
        _app.removeEventFilter(tracer)
    lines = [r.getMessage() for r in caplog.records if r.name == "window_trace"]
    assert any("SHOW" in m and "QLabel" in m for m in lines)
    assert any("HIDE" in m and "visible=" in m for m in lines)
    assert not any("Иванов" in m or "445" in m for m in lines)
