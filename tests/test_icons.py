"""Shared icon set: every named icon draws, statuses are distinct, no emoji/SP_* left in the UI."""
import glob
import io
import re

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from utils import icons

NAV_NAMES = [
    "entry", "view", "transfer", "journal", "summary", "protocols", "quick", "settings", "help", "org",
    "plus", "close", "check", "upload", "download", "file", "search", "refresh", "copy", "chevron", "more",
    "print", "code", "lock", "clock", "shield", "key", "heart", "folder", "warn", "circle",
]
STATUS_KINDS = ["ok", "warn", "deleted", "not_trained", "pending", "unknown", "signed", "unsigned"]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("name", NAV_NAMES)
def test_every_nav_icon_has_a_drawing(app, name):
    assert icons._icon_paths(name), name
    assert not icons.nav_icon(name, QColor("#000000")).isNull()


@pytest.mark.parametrize("kind", STATUS_KINDS)
def test_status_icons_draw(app, kind):
    assert not icons.status_icon(kind).isNull()


def test_not_trained_is_a_plain_red_circle(app):
    img = icons.status_icon("not_trained", 32).pixmap(32, 32).toImage()
    centre = img.pixelColor(img.width() // 2, img.height() // 2)
    assert centre.name().upper() == icons.STATUS_RED


def test_status_icons_differ(app):
    shots = {k: icons.status_icon(k, 32).pixmap(32, 32).toImage() for k in ("ok", "warn", "deleted", "pending")}
    kinds = list(shots)
    for i, a in enumerate(kinds):
        for b in kinds[i + 1:]:
            assert shots[a] != shots[b], (a, b)


def test_themed_icon_uses_current_theme(app):
    assert not icons.themed_icon("check", "ok_text").isNull()


EMOJI = re.compile("[\U0001F000-\U0001FFFF☀-➿⬀-⯿✅❌⚠✔✖️]")


def test_no_emoji_or_standard_pixmaps_in_ui_code():
    offenders = []
    for path in glob.glob("tabs/*.py") + glob.glob("utils/*.py") + ["main.py"]:
        for no, line in enumerate(io.open(path, encoding="utf-8"), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""'):
                continue
            if EMOJI.search(line) or re.search(r"\bSP_[A-Z]", line):
                offenders.append("%s:%d" % (path, no))
    assert not offenders, offenders
