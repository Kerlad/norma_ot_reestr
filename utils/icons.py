"""Small vector icons drawn with QPainter (no image files, no QtSvg)."""
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF, QBrush
from PySide6.QtWidgets import QApplication

STATUS_COLORS = {
    "signed": "#2e9e4f",
    "deleted": "#d03535",
    "unsigned": "#e0a800",
    "unknown": "#8a8f98",
}


def _dpr() -> float:
    app = QApplication.instance()
    screen = app.primaryScreen() if app else None
    return screen.devicePixelRatio() if screen else 1.0


def _canvas(size: int):
    dpr = _dpr()
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pm, p


def eye_icon(color: QColor, crossed: bool = False, size: int = 20) -> QIcon:
    pm, p = _canvas(size)
    pen = QPen(color, max(1.4, size / 12.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    w = float(size)
    p.drawEllipse(QRectF(w * 0.08, w * 0.27, w * 0.84, w * 0.46))
    p.setBrush(QBrush(color))
    r = w * 0.12
    p.drawEllipse(QPointF(w / 2, w / 2), r, r)
    if crossed:
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(w * 0.14, w * 0.86), QPointF(w * 0.86, w * 0.14))
    p.end()
    return QIcon(pm)


def status_icon(kind: str, size: int = 16) -> QIcon:
    """signed = green check, deleted = red cross, unsigned = yellow triangle, unknown = grey '?'."""
    color = QColor(STATUS_COLORS.get(kind, STATUS_COLORS["unknown"]))
    pm, p = _canvas(size)
    w = float(size)
    pen = QPen(color, max(1.6, w / 8.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    if kind == "signed":
        p.drawPolyline(QPolygonF([QPointF(w * 0.18, w * 0.54), QPointF(w * 0.42, w * 0.78),
                                  QPointF(w * 0.84, w * 0.24)]))
    elif kind == "deleted":
        p.drawLine(QPointF(w * 0.22, w * 0.22), QPointF(w * 0.78, w * 0.78))
        p.drawLine(QPointF(w * 0.78, w * 0.22), QPointF(w * 0.22, w * 0.78))
    elif kind == "unsigned":
        p.setBrush(QBrush(color))
        p.drawPolygon(QPolygonF([QPointF(w * 0.5, w * 0.1), QPointF(w * 0.92, w * 0.86),
                                 QPointF(w * 0.08, w * 0.86)]))
        p.setPen(QPen(QColor("#ffffff"), max(1.4, w / 9.0), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(w * 0.5, w * 0.38), QPointF(w * 0.5, w * 0.62))
        p.drawPoint(QPointF(w * 0.5, w * 0.76))
    else:
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(w * 0.12, w * 0.12, w * 0.76, w * 0.76))
        f = p.font()
        f.setPixelSize(max(8, int(w * 0.6)))
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, 0, w, w), Qt.AlignmentFlag.AlignCenter, "?")
    p.end()
    return QIcon(pm)
