"""Diagnostics: log every top-level window shown or hidden (hunt for windows that flash at startup).

Enabled by the environment variable NORMAOT_TRACE_WINDOWS=1; the lines go to the app log (log/).
Logs class names, object names, geometry and the app source lines that caused the event — never
window titles or texts (they may contain personal data).
"""
import logging
import os
import time
import traceback

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QWidget

logger = logging.getLogger("window_trace")

ENV_VAR = "NORMAOT_TRACE_WINDOWS"
_APP_ROOT = os.path.normcase(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def enabled() -> bool:
    return os.environ.get(ENV_VAR, "").strip() not in ("", "0")


def _app_frames(limit: int = 4) -> str:
    frames = [f for f in traceback.extract_stack()[:-3]
              if os.path.normcase(os.path.abspath(f.filename)).startswith(_APP_ROOT)
              and not f.filename.endswith("window_trace.py")]
    return " <- ".join("%s:%d" % (os.path.basename(f.filename), f.lineno) for f in frames[-limit:][::-1])


class WindowTracer(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._t0 = time.perf_counter()
        self._shown = {}

    def eventFilter(self, obj, event):
        et = event.type()
        if et in (QEvent.Type.Show, QEvent.Type.Hide) and isinstance(obj, QWidget) and obj.isWindow():
            try:
                now = time.perf_counter() - self._t0
                key = id(obj)
                extra = ""
                if et == QEvent.Type.Show:
                    self._shown[key] = now
                else:
                    started = self._shown.pop(key, None)
                    if started is not None:
                        extra = " visible=%.3fs" % (now - started)
                g = obj.geometry()
                logger.info("WINDOW %s t=%.3f %s name=%s parent=%s geom=%dx%d+%d+%d%s at %s",
                            "SHOW" if et == QEvent.Type.Show else "HIDE", now, type(obj).__name__,
                            obj.objectName() or "-", type(obj.parent()).__name__ if obj.parent() else "None",
                            g.width(), g.height(), g.x(), g.y(), extra, _app_frames() or "-")
            except Exception as e:  # diagnostics must never break the app
                logger.debug("window trace failed: %s", type(e).__name__)
        return False


def install(app) -> bool:
    """Installs the tracer on the QApplication when the env variable is set."""
    if not enabled():
        return False
    tracer = WindowTracer(app)
    app.installEventFilter(tracer)
    logger.info("Window trace enabled (%s)", ENV_VAR)
    return True
