"""Small vector icons drawn with QPainter (no image files, no QtSvg)."""
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QBrush
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


# ---- navigation / action icons (24x24 grid, stroke only, colour comes from the theme) ----

def _poly(*pts):
    path = QPainterPath()
    path.moveTo(*pts[0])
    for pt in pts[1:]:
        path.lineTo(*pt)
    return path


def _icon_paths(name: str):
    """Returns a list of QPainterPath on a 24x24 grid (open strokes)."""
    paths = []
    if name == "entry":  # pencil
        paths.append(_poly((4, 20), (5, 15), (16, 4), (20, 8), (9, 19), (4, 20)))
        paths.append(_poly((14, 6), (18, 10)))
    elif name == "view":  # table
        path = QPainterPath()
        path.addRoundedRect(QRectF(3, 5, 18, 14), 2, 2)
        paths.append(path)
        paths.append(_poly((3, 10), (21, 10)))
        paths.append(_poly((9, 10), (9, 19)))
    elif name == "transfer":  # paper plane
        paths.append(_poly((21, 3), (3, 10), (10, 13), (13, 20), (21, 3)))
        paths.append(_poly((21, 3), (10, 13)))
    elif name == "journal":  # book
        paths.append(_poly((5, 4), (18, 4), (18, 20), (7, 20), (5, 18), (5, 4)))
        paths.append(_poly((9, 8), (14, 8)))
        paths.append(_poly((9, 12), (14, 12)))
    elif name == "summary":  # people
        c1 = QPainterPath()
        c1.addEllipse(QRectF(8, 4, 6, 6))
        paths.append(c1)
        paths.append(_poly((3, 20), (4, 15), (7, 13), (15, 13), (18, 15), (19, 20)))
    elif name == "protocols":  # sliders
        for y, x in ((7, 9), (12, 15), (17, 7)):
            paths.append(_poly((4, y), (20, y)))
            knob = QPainterPath()
            knob.addEllipse(QRectF(x - 2, y - 2, 4, 4))
            paths.append(knob)
    elif name == "quick":  # bolt
        paths.append(_poly((13, 2), (5, 13), (11, 13), (10, 22), (19, 10), (13, 10), (13, 2)))
    elif name == "settings":  # gear
        ring = QPainterPath()
        ring.addEllipse(QRectF(9, 9, 6, 6))
        paths.append(ring)
        import math
        for k in range(8):
            a = math.pi * k / 4
            paths.append(_poly((12 + 6.5 * math.cos(a), 12 + 6.5 * math.sin(a)),
                               (12 + 9.5 * math.cos(a), 12 + 9.5 * math.sin(a))))
    elif name == "help":
        ring = QPainterPath()
        ring.addEllipse(QRectF(3, 3, 18, 18))
        paths.append(ring)
        paths.append(_poly((9.5, 9.5), (10, 8), (12, 7), (14, 8), (14.5, 10), (12, 12), (12, 14)))
        paths.append(_poly((12, 17), (12, 17.2)))
    elif name == "org":  # building
        paths.append(_poly((5, 21), (5, 4), (15, 4), (15, 21)))
        paths.append(_poly((15, 10), (19, 10), (19, 21)))
        paths.append(_poly((3, 21), (21, 21)))
        paths.append(_poly((9, 8), (11, 8)))
        paths.append(_poly((9, 12), (11, 12)))
        paths.append(_poly((9, 16), (11, 16)))
    elif name == "chevron":
        paths.append(_poly((6, 9), (12, 15), (18, 9)))
    elif name == "warn":
        paths.append(_poly((12, 3), (22, 20), (2, 20), (12, 3)))
        paths.append(_poly((12, 10), (12, 14)))
        paths.append(_poly((12, 17), (12, 17.2)))
    elif name == "circle":
        ring = QPainterPath()
        ring.addEllipse(QRectF(4, 4, 16, 16))
        paths.append(ring)
    return paths


def nav_icon(name: str, color: QColor, size: int = 20) -> QIcon:
    """Stroke icon from the shared set; recreate on theme change (colour is baked in)."""
    pm, p = _canvas(size)
    pen = QPen(QColor(color), 1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.scale(size / 24.0, size / 24.0)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for path in _icon_paths(name):
        p.drawPath(path)
    p.end()
    return QIcon(pm)
