"""Small vector icons drawn with QPainter (no image files, no QtSvg)."""
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QBrush
from PySide6.QtWidgets import QApplication

# Status fills are the same in every theme (spec, section 2)
STATUS_GREEN = "#1E8E3E"
STATUS_YELLOW = "#F2A900"
STATUS_YELLOW_MARK = "#3A2A00"
STATUS_RED = "#C62828"
STATUS_GREY = "#8A8F98"

# kind -> canonical status; the first four are the send-history names
_STATUS_ALIASES = {
    "signed": "ok", "unsigned": "warn", "deleted": "deleted", "unknown": "unknown",
    "ok": "ok", "warn": "warn", "not_trained": "not_trained", "pending": "pending",
    "expired": "warn", "trained": "ok",
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
    """Filled status icons: ok = green circle with a check, warn = yellow triangle with '!',
    deleted = red circle with a cross, not_trained = red circle without a mark [owner],
    pending = grey circle with a clock, unknown = grey circle with '?'."""
    kind = _STATUS_ALIASES.get(kind, "unknown")
    pm, p = _canvas(size)
    w = float(size)
    white = QColor("#FFFFFF")

    def mark_pen(color):
        pen = QPen(QColor(color), max(1.5, w / 9.0))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    def disc(color):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(color)))
        p.drawEllipse(QRectF(w * 0.06, w * 0.06, w * 0.88, w * 0.88))
        p.setBrush(Qt.BrushStyle.NoBrush)

    if kind == "ok":
        disc(STATUS_GREEN)
        p.setPen(mark_pen(white))
        p.drawPolyline(QPolygonF([QPointF(w * 0.28, w * 0.52), QPointF(w * 0.44, w * 0.67),
                                  QPointF(w * 0.72, w * 0.36)]))
    elif kind == "warn":
        p.setPen(QPen(QColor(STATUS_YELLOW), max(1.0, w / 14.0), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(QBrush(QColor(STATUS_YELLOW)))
        p.drawPolygon(QPolygonF([QPointF(w * 0.5, w * 0.1), QPointF(w * 0.93, w * 0.86),
                                 QPointF(w * 0.07, w * 0.86)]))
        p.setPen(mark_pen(STATUS_YELLOW_MARK))
        p.drawLine(QPointF(w * 0.5, w * 0.38), QPointF(w * 0.5, w * 0.60))
        p.drawPoint(QPointF(w * 0.5, w * 0.74))
    elif kind == "deleted":
        disc(STATUS_RED)
        p.setPen(mark_pen(white))
        p.drawLine(QPointF(w * 0.34, w * 0.34), QPointF(w * 0.66, w * 0.66))
        p.drawLine(QPointF(w * 0.66, w * 0.34), QPointF(w * 0.34, w * 0.66))
    elif kind == "not_trained":
        disc(STATUS_RED)
    elif kind == "pending":
        disc(STATUS_GREY)
        p.setPen(mark_pen(white))
        p.drawPolyline(QPolygonF([QPointF(w * 0.5, w * 0.28), QPointF(w * 0.5, w * 0.5),
                                  QPointF(w * 0.66, w * 0.6)]))
    else:
        disc(STATUS_GREY)
        p.setPen(mark_pen(white))
        question = QPainterPath()
        question.moveTo(w * 0.38, w * 0.38)
        question.cubicTo(w * 0.38, w * 0.20, w * 0.64, w * 0.20, w * 0.64, w * 0.38)
        question.cubicTo(w * 0.64, w * 0.50, w * 0.50, w * 0.50, w * 0.50, w * 0.62)
        p.drawPath(question)
        p.drawPoint(QPointF(w * 0.50, w * 0.76))
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
    elif name == "info":
        ring = QPainterPath()
        ring.addEllipse(QRectF(3, 3, 18, 18))
        paths.append(ring)
        paths.append(_poly((12, 11), (12, 17)))
        paths.append(_poly((12, 7.5), (12, 7.7)))
    elif name == "org":  # building
        paths.append(_poly((5, 21), (5, 4), (15, 4), (15, 21)))
        paths.append(_poly((15, 10), (19, 10), (19, 21)))
        paths.append(_poly((3, 21), (21, 21)))
        paths.append(_poly((9, 8), (11, 8)))
        paths.append(_poly((9, 12), (11, 12)))
        paths.append(_poly((9, 16), (11, 16)))
    elif name == "plus":
        paths.append(_poly((12, 5), (12, 19)))
        paths.append(_poly((5, 12), (19, 12)))
    elif name == "close":
        paths.append(_poly((6, 6), (18, 18)))
        paths.append(_poly((18, 6), (6, 18)))
    elif name == "check":
        paths.append(_poly((5, 12.5), (10, 17.5), (19, 7)))
    elif name == "upload":
        paths.append(_poly((12, 16), (12, 4)))
        paths.append(_poly((7, 9), (12, 4), (17, 9)))
        paths.append(_poly((4, 16), (4, 20), (20, 20), (20, 16)))
    elif name == "download":
        paths.append(_poly((12, 4), (12, 16)))
        paths.append(_poly((7, 11), (12, 16), (17, 11)))
        paths.append(_poly((4, 16), (4, 20), (20, 20), (20, 16)))
    elif name == "file":
        paths.append(_poly((6, 3), (14, 3), (19, 8), (19, 21), (6, 21), (6, 3)))
        paths.append(_poly((14, 3), (14, 8), (19, 8)))
    elif name == "search":
        ring = QPainterPath()
        ring.addEllipse(QRectF(4, 4, 11, 11))
        paths.append(ring)
        paths.append(_poly((13, 13), (20, 20)))
    elif name == "refresh":
        arc = QPainterPath()
        arc.arcMoveTo(QRectF(4, 4, 16, 16), 40)
        arc.arcTo(QRectF(4, 4, 16, 16), 40, 280)
        paths.append(arc)
        paths.append(_poly((17.5, 3), (18.5, 8), (13.5, 8.5)))
    elif name == "copy":
        back = QPainterPath()
        back.addRoundedRect(QRectF(9, 9, 11, 11), 2, 2)
        paths.append(back)
        paths.append(_poly((5, 15), (5, 5), (15, 5)))
    elif name == "more":
        for x in (6, 12, 18):
            paths.append(_poly((x, 12), (x, 12.2)))
    elif name == "print":
        paths.append(_poly((7, 9), (7, 3), (17, 3), (17, 9)))
        body = QPainterPath()
        body.addRoundedRect(QRectF(3, 9, 18, 8), 2, 2)
        paths.append(body)
        paths.append(_poly((7, 14), (17, 14), (17, 21), (7, 21), (7, 14)))
    elif name == "code":
        paths.append(_poly((8, 7), (3, 12), (8, 17)))
        paths.append(_poly((16, 7), (21, 12), (16, 17)))
        paths.append(_poly((14, 5), (10, 19)))
    elif name == "lock":
        body = QPainterPath()
        body.addRoundedRect(QRectF(5, 11, 14, 10), 2, 2)
        paths.append(body)
        shackle = QPainterPath()
        shackle.moveTo(8, 11)
        shackle.lineTo(8, 8)
        shackle.arcTo(QRectF(8, 3, 8, 8), 180, -180)
        shackle.lineTo(16, 11)
        paths.append(shackle)
    elif name == "clock":
        ring = QPainterPath()
        ring.addEllipse(QRectF(3, 3, 18, 18))
        paths.append(ring)
        paths.append(_poly((12, 7), (12, 12), (16, 14)))
    elif name == "shield":
        paths.append(_poly((12, 3), (20, 6), (20, 12), (17, 18), (12, 21), (7, 18), (4, 12), (4, 6), (12, 3)))
        paths.append(_poly((8.5, 12), (11, 14.5), (15.5, 9.5)))
    elif name == "key":
        ring = QPainterPath()
        ring.addEllipse(QRectF(3, 11, 7, 7))
        paths.append(ring)
        paths.append(_poly((9.5, 12), (20, 4)))
        paths.append(_poly((16, 7), (18, 9)))
    elif name == "heart":
        heart = QPainterPath()
        heart.moveTo(12, 20)
        heart.cubicTo(2, 13, 4, 4, 12, 8.5)
        heart.cubicTo(20, 4, 22, 13, 12, 20)
        paths.append(heart)
    elif name == "folder":
        paths.append(_poly((3, 6), (9, 6), (11, 8), (21, 8), (21, 19), (3, 19), (3, 6)))
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


def themed_icon(name: str, token: str = "text", size: int = 18) -> QIcon:
    """nav_icon coloured with a token of the current theme (baked in: recreate on theme change)."""
    from utils.tahoe_style import get_colors, get_current_theme
    return nav_icon(name, QColor(get_colors(get_current_theme()).tokens[token]), size)
