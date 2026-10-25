"""Theme tokens: registry, legacy migration, contrast, stylesheet build."""
import json
import re

import pytest

from utils import tahoe_style as ts


def _lum(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_registry_has_three_themes():
    assert ts.THEME_ORDER == ["norma", "monokaiDark", "monokaiLight"]
    assert set(ts.THEME_LABELS) == set(ts.THEME_ORDER)


@pytest.mark.parametrize("old,new", [
    ("light", "norma"), ("dark", "monokaiDark"), ("dracula", "monokaiDark"),
    ("monokai", "monokaiLight"), ("garbage", "norma"), (None, "norma"), ("norma", "norma"),
])
def test_legacy_theme_keys_are_migrated(old, new):
    assert ts.normalize_theme(old) == new


def test_load_theme_migrates_legacy_file(tmp_path):
    path = ts.get_theme_file(str(tmp_path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"theme": "dracula"}, f)
    assert ts.load_theme(str(tmp_path)) == "monokaiDark"


@pytest.mark.parametrize("theme", ts.THEME_ORDER)
def test_tokens_are_six_digit_hex_and_complete(theme):
    keys = set(ts._NORMA_TOKENS)
    tokens = ts.get_colors(theme).tokens
    assert set(tokens) == keys
    assert all(re.fullmatch(r"#[0-9A-Fa-f]{6}", v) for v in tokens.values())


@pytest.mark.parametrize("theme", ts.THEME_ORDER)
def test_text_contrast(theme):
    t = ts.get_colors(theme).tokens
    pairs = [("text", "surface"), ("text", "page"), ("text_muted", "surface"),
             ("on_cta", "cta"), ("on_dark", "dark_btn"), ("side_text", "side_bg"),
             ("side_active_fg", "side_active_bg")]
    for fg, bg in pairs:
        assert _ratio(t[fg], t[bg]) >= 4.5, (theme, fg, bg, _ratio(t[fg], t[bg]))
    # status chips are bold, short labels: large-text threshold (palette approved by the owner;
    # monokaiDark err_text/err_bg is ~3.5:1)
    for fg, bg in [("ok_text", "ok_bg"), ("warn_text", "warn_bg"), ("err_text", "err_bg")]:
        assert _ratio(t[fg], t[bg]) >= 3.0, (theme, fg, bg, _ratio(t[fg], t[bg]))


@pytest.mark.parametrize("theme", ts.THEME_ORDER)
def test_stylesheet_builds_without_leftover_braces(theme):
    qss = ts.get_global_stylesheet(theme)
    assert 'QPushButton[role="primary"]' in qss
    assert "{c." not in qss and "primary_hex" not in qss
    assert ts.get_current_theme() == theme
