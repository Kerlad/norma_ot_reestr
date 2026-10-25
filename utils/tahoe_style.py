"""
Дизайн-система «Норма» для PySide6: токены трёх тем, палитра, глобальный QSS
"""
import sys
import os
import json
import ctypes
import logging

from PySide6.QtGui import QPalette, QColor

logger = logging.getLogger(__name__)


# ============ ТОКЕНЫ ТЕМ («Норма», Monokai тёмная, Monokai светлая) ============
# Единственный источник цветов. Значения — по INFO/REDESIGN_3.9.9_SPEC.md, раздел 2.
# Только 6-значный hex (в QSS к ним дописывается альфа-суффикс).

_NORMA_TOKENS = {
    "page": "#F5F3F9", "surface": "#FFFFFF", "surface_subtle": "#FBFAFD", "segment_bg": "#F1EEF8",
    "border": "#E4E0EE", "border_input": "#D5CFE3", "divider": "#EEEAF5", "divider_row": "#F2EFF7",
    "text": "#1C1730", "text_secondary": "#3B3452", "text_muted": "#5E5873",
    "text_faint": "#8A83A0", "text_faint2": "#A29CB5",
    "cta": "#C2EF4E", "on_cta": "#1A1330", "dark_btn": "#1A1330", "on_dark": "#FFFFFF",
    "link": "#5B3FD1", "link_hover": "#4630A8", "selection": "#EEEAFB", "selection_row": "#F3F0FC",
    "side_bg": "#1A1330", "side_text": "#CFC8E3", "side_muted": "#A79FC2", "side_strong": "#FFFFFF",
    "side_line": "#3A2F5C", "side_btn": "#241B40", "side_active_bg": "#2B2150", "side_active_fg": "#C2EF4E",
    "ok_text": "#1E6B34", "ok_bg": "#E9F7EC", "warn_text": "#7A4D00", "warn_bg": "#FFF4D6",
    "err_text": "#A61B1B", "err_bg": "#FDECEC",
}

_MONOKAI_DARK_TOKENS = {
    "page": "#272822", "surface": "#2D2E27", "surface_subtle": "#2A2B24", "segment_bg": "#3E3D32",
    "border": "#3E3D32", "border_input": "#57584F", "divider": "#3E3D32", "divider_row": "#34352D",
    "text": "#F8F8F2", "text_secondary": "#CFCFC2", "text_muted": "#A59F85",
    "text_faint": "#90908A", "text_faint2": "#75715E",
    "cta": "#A6E22E", "on_cta": "#272822", "dark_btn": "#49483E", "on_dark": "#F8F8F2",
    "link": "#AE81FF", "link_hover": "#C9A8FF", "selection": "#3B3550", "selection_row": "#383541",
    "side_bg": "#1E1F1C", "side_text": "#CFCFC2", "side_muted": "#9D9A88", "side_strong": "#F8F8F2",
    "side_line": "#3E3D32", "side_btn": "#272822", "side_active_bg": "#3E3D32", "side_active_fg": "#A6E22E",
    "ok_text": "#A6E22E", "ok_bg": "#2F3A26", "warn_text": "#E6DB74", "warn_bg": "#3D3622",
    "err_text": "#F92672", "err_bg": "#3F2A2C",
}

_MONOKAI_LIGHT_TOKENS = {
    "page": "#FAF4F2", "surface": "#FFFFFF", "surface_subtle": "#FBF8F7", "segment_bg": "#F1EAE7",
    "border": "#E8DEDA", "border_input": "#D3C9C5", "divider": "#F1EAE7", "divider_row": "#F4EEEB",
    "text": "#29242A", "text_secondary": "#4A4448", "text_muted": "#6E676A",
    "text_faint": "#8A8486", "text_faint2": "#A39A9D",
    "cta": "#C9305E", "on_cta": "#FFFFFF", "dark_btn": "#29242A", "on_dark": "#FFFFFF",
    "link": "#7058BE", "link_hover": "#5A43A3", "selection": "#EEE9FA", "selection_row": "#F5F0FB",
    "side_bg": "#EDE7E5", "side_text": "#403E41", "side_muted": "#6E676A", "side_strong": "#29242A",
    "side_line": "#DDD5D2", "side_btn": "#F8F3F1", "side_active_bg": "#FFFFFF", "side_active_fg": "#C9305E",
    "ok_text": "#1E7A4E", "ok_bg": "#E5F4EC", "warn_text": "#8A5A00", "warn_bg": "#FCF1D9",
    "err_text": "#B3264F", "err_bg": "#FBE7EC",
}


class ThemeColors:
    """Цвета темы: токены (атрибуты в нижнем регистре) + прежние имена для существующего QSS/кода."""

    def __init__(self, tokens: dict):
        self.tokens = dict(tokens)
        for name, value in tokens.items():
            setattr(self, name, value)
        t = self.tokens
        self.PRIMARY = t["link"]
        self.SECONDARY = t["link_hover"]
        self.ACCENT = t["cta"]
        self.SUCCESS = t["ok_text"]
        self.WARNING = t["warn_text"]
        self.ERROR = t["err_text"]
        self.TEXT_PRIMARY = t["text"]
        self.TEXT_SECONDARY = t["text_muted"]
        self.TEXT_ON_ACCENT = t["on_dark"]
        self.TEXT_DISABLED = t["text_faint"]
        self.TEXT_PLACEHOLDER = t["text_faint"]
        self.WINDOW_BG = t["page"]
        self.SURFACE_BG = t["surface"]
        self.INPUT_BG = t["surface"]
        self.MENU_BG = t["surface"]
        self.TABLE_ALTERNATE = t["surface_subtle"]
        self.BORDER_LIGHT = t["border"]
        self.BORDER_INPUT = t["border_input"]
        self.BORDER_SUBTLE = t["border"]
        self.SCROLLBAR_HANDLE = t["border_input"]
        self.SCROLLBAR_HOVER = t["text_faint"]
        self.HIGHLIGHT_BG = t["selection_row"]
        self.HIGHLIGHT_SELECTED = t["selection"]
        self.GLASS_DARK = t["dark_btn"]


# ============ РЕЕСТР ТЕМ ============

DEFAULT_THEME = "norma"

THEME_ORDER = ["norma", "monokaiDark", "monokaiLight"]

THEME_LABELS = {
    "norma": "Норма",
    "monokaiDark": "Monokai тёмная",
    "monokaiLight": "Monokai светлая",
}

_DARK_THEMES = {"monokaiDark"}

_THEME_TOKENS = {
    "norma": _NORMA_TOKENS,
    "monokaiDark": _MONOKAI_DARK_TOKENS,
    "monokaiLight": _MONOKAI_LIGHT_TOKENS,
}

# Ключи тем до 3.9.0 -> ближайшая новая тема
_LEGACY_THEME_MAP = {
    "light": "norma",
    "dark": "monokaiDark",
    "dracula": "monokaiDark",
    "monokai": "monokaiLight",
}


def normalize_theme(theme) -> str:
    """Старый или неизвестный ключ темы -> ключ из THEME_ORDER."""
    if theme in _THEME_TOKENS:
        return theme
    return _LEGACY_THEME_MAP.get(theme, DEFAULT_THEME)


def is_dark_theme(theme: str) -> bool:
    """Тёмная ли это тема (влияет на рамки/фоны)."""
    return normalize_theme(theme) in _DARK_THEMES


def get_colors(theme: str) -> ThemeColors:
    """Возвращает объект цветов для темы."""
    return ThemeColors(_THEME_TOKENS[normalize_theme(theme)])


_CURRENT_THEME = DEFAULT_THEME


def set_current_theme(theme: str) -> None:
    """Запоминает активную тему (для тема-зависимых цветов моделей)."""
    global _CURRENT_THEME
    _CURRENT_THEME = normalize_theme(theme)


def get_current_theme() -> str:
    return _CURRENT_THEME


def get_journal_status_colors(status: str):
    """Цвета (фон, текст) ячеек журнала с учётом текущей темы."""
    c = get_colors(_CURRENT_THEME)
    if status == "pending":
        return QColor(c.warn_bg), QColor(c.warn_text)
    return QColor(c.ok_bg), QColor(c.ok_text)


# ============ QPALETTE ============

def create_palette(theme: str = DEFAULT_THEME) -> QPalette:
    """
    Создаёт QPalette с полным набором ColorRole.
    Включает Normal, Disabled, Inactive группы для корректной работы Fusion style.
    """
    theme = normalize_theme(theme)
    return _build_palette_from_colors(get_colors(theme), is_dark_theme(theme))


def _build_palette_from_colors(c, dark: bool) -> QPalette:
    """Строит QPalette из объекта цветов темы."""
    p = QPalette()
    window = QColor(c.WINDOW_BG)
    base = QColor(c.INPUT_BG)
    surface = QColor(c.SURFACE_BG)
    text = QColor(c.TEXT_PRIMARY)
    primary = QColor(c.PRIMARY)
    on_accent = QColor(c.TEXT_ON_ACCENT)
    placeholder = QColor(c.TEXT_PLACEHOLDER)
    alt = surface.lighter(112) if dark else surface.darker(104)
    disabled = QColor("#777777") if dark else QColor("#A0A0AA")
    disabled_hl = surface.lighter(120) if dark else surface.darker(110)
    disabled_base = window.darker(112) if dark else window.darker(105)

    # Normal
    p.setColor(QPalette.ColorRole.Window,          window)
    p.setColor(QPalette.ColorRole.WindowText,      text)
    p.setColor(QPalette.ColorRole.Base,            base)
    p.setColor(QPalette.ColorRole.AlternateBase,   alt)
    p.setColor(QPalette.ColorRole.Text,            text)
    p.setColor(QPalette.ColorRole.Button,          surface)
    p.setColor(QPalette.ColorRole.ButtonText,      text)
    p.setColor(QPalette.ColorRole.BrightText,      QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Highlight,       primary)
    p.setColor(QPalette.ColorRole.HighlightedText, on_accent)
    p.setColor(QPalette.ColorRole.Link,            primary)
    p.setColor(QPalette.ColorRole.LinkVisited,     primary)
    p.setColor(QPalette.ColorRole.PlaceholderText, placeholder)

    # Disabled
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText,      disabled)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,            disabled)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText,      disabled)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight,       disabled_hl)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, disabled)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base,            disabled_base)

    # Inactive
    inactive_hl = QColor(primary)
    inactive_hl.setAlpha(100)
    p.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight,       inactive_hl)
    p.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.HighlightedText, on_accent)

    return p


# ============ ГЛОБАЛЬНЫЙ STYLESHEET ============

def get_global_stylesheet(theme: str = DEFAULT_THEME) -> str:
    """Глобальная QSS-stylesheet. theme: ключ темы из THEME_ORDER."""
    set_current_theme(theme)
    c = get_colors(theme)
    dark = is_dark_theme(theme)

    primary_hex = c.link
    highlight_bg = c.HIGHLIGHT_BG
    highlight_sel = c.HIGHLIGHT_SELECTED

    return f"""
        QMainWindow,
        QDialog {{
            background-color: {c.WINDOW_BG};
        }}

        QWidget {{
            color: {c.TEXT_PRIMARY};
            font-family: "Rubik", "Segoe UI", "Noto Sans", sans-serif;
            font-size: 13px;
        }}

        /* ============ QGroupBox ============ */
        QGroupBox {{
            background-color: {c.SURFACE_BG};
            border: 1px solid {c.BORDER_LIGHT};
            border-radius: 10px;
            margin-top: 14px;
            padding: 18px 16px 16px 16px;
            font-weight: bold;
            font-size: 14px;
            color: {c.PRIMARY};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 8px;
            color: {c.PRIMARY};
            font-weight: bold;
        }}

        /* ============ QPushButton ============ */
        QPushButton {{
            background-color: {c.SURFACE_BG};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 8px;
            padding: 7px 18px;
            font-weight: bold;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {highlight_bg};
            border-color: {c.PRIMARY};
        }}
        QPushButton:pressed {{
            background-color: {highlight_sel};
            padding-top: 8px;
            padding-bottom: 6px;
        }}
        QPushButton:disabled {{
            color: {c.TEXT_DISABLED} !important;
            background-color: {c.SURFACE_BG};
            border-color: {c.BORDER_LIGHT};
        }}

        QPushButton[primary="true"] {{
            background-color: {c.cta};
            color: {c.on_cta};
            border: none;
        }}
        QPushButton[primary="true"]:hover {{
            background-color: {c.cta};
        }}
        QPushButton[primary="true"]:pressed {{
            background-color: {c.cta};
            padding-top: 8px;
            padding-bottom: 6px;
        }}

        QPushButton[success="true"] {{
            background-color: {c.cta};
            color: {c.on_cta};
            border: none;
        }}
        QPushButton[success="true"]:hover {{
            background-color: {c.cta};
        }}
        QPushButton[success="true"]:pressed {{
            background-color: {c.cta};
            padding-top: 8px;
            padding-bottom: 6px;
        }}

        QPushButton[danger="true"] {{
            background-color: transparent;
            color: {c.ERROR};
            border: 1.5px solid {c.ERROR};
        }}
        QPushButton[danger="true"]:hover {{
            background-color: {c.ERROR}22;
        }}
        QPushButton[danger="true"]:pressed {{
            background-color: {c.ERROR}44;
        }}

        /* Роли кнопок: btn.setProperty("role", ...) */
        QPushButton[role="primary"] {{
            background-color: {c.cta};
            color: {c.on_cta};
            border: none;
            min-height: 20px;
        }}
        QPushButton[role="primary"]:hover {{ background-color: {c.cta}; }}
        QPushButton[role="dark"] {{
            background-color: {c.dark_btn};
            color: {c.on_dark};
            border: none;
        }}
        QPushButton[role="dark"]:hover {{ background-color: {c.dark_btn}; }}
        QPushButton[role="secondary"] {{
            background-color: {c.surface};
            color: {c.text};
            border: 1px solid {c.border_input};
        }}
        QPushButton[role="ghost"] {{
            background-color: transparent;
            color: {c.text_muted};
            border: none;
        }}
        QPushButton[role="ghost"]:hover {{
            background-color: {c.selection};
            color: {c.link_hover};
        }}
        QPushButton[role="danger"] {{
            background-color: {c.err_bg};
            color: {c.err_text};
            border: 1px solid {c.err_text};
        }}

        /* ============ ProtocolTab member cards ============ */
        #memberCard {{
            background-color: {c.SURFACE_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 8px;
        }}
        #memberRemoveBtn {{
            background-color: transparent;
            color: {c.ERROR};
            border: 1px solid {c.ERROR};
            border-radius: 4px;
            font-weight: bold;
            font-size: 12px;
            padding: 0;
            min-width: 24px;
            min-height: 24px;
        }}
        #memberRemoveBtn:hover {{
            background-color: {c.err_bg};
        }}
        #addMemberBtn {{
            background-color: transparent;
            color: {c.PRIMARY};
            border: 1px dashed {c.BORDER_INPUT};
            border-radius: 6px;
            padding: 6px 14px;
            font-weight: normal;
        }}
        #addMemberBtn:hover {{
            background-color: {highlight_bg};
            border-color: {c.PRIMARY};
            border-style: solid;
        }}

        /* ============ ProtocolTab action buttons ============ */
        #saveCommissionBtn {{
            background-color: {c.cta};
            color: {c.on_cta};
            border: none;
            padding: 8px 22px;
        }}
        #saveCommissionBtn:hover {{
            background-color: {c.cta};
        }}
        #saveCommissionBtn:pressed {{
            background-color: {c.cta};
            padding-top: 9px;
            padding-bottom: 7px;
        }}

        #loadCommissionBtn {{
            background-color: {c.SURFACE_BG};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER_INPUT};
        }}
        #loadCommissionBtn:hover {{
            background-color: {highlight_bg};
            border-color: {c.PRIMARY};
        }}

        #generateProtocolBtn {{
            background-color: {c.cta};
            color: {c.on_cta};
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            padding: 14px 32px;
        }}
        #generateProtocolBtn:hover {{
            background-color: {c.SUCCESS};
        }}
        #generateProtocolBtn:pressed {{
            background-color: {c.SUCCESS};
            padding-top: 15px;
            padding-bottom: 13px;
        }}

        /* ============ SingleWorkerProtocolTab ============ */
        #workerFormCard {{
            background-color: {c.SURFACE_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 10px;
        }}
        #programHelpBtn {{
            background-color: {c.SURFACE_BG};
            color: {c.PRIMARY};
            border: 1px solid {c.PRIMARY};
            border-radius: 6px;
            padding: 5px 14px;
            font-weight: normal;
        }}
        #programHelpBtn:hover {{
            background-color: {highlight_bg};
        }}
        #previewLabel {{
            color: {c.TEXT_SECONDARY};
            font-size: 12px;
            padding: 2px 4px;
            background-color: transparent;
        }}

        /* ============ ProtocolTab programs tab ============ */
        #programsHint {{
            color: {c.TEXT_SECONDARY};
            font-size: 12px;
            padding: 4px 0;
            background-color: transparent;
        }}
        #programsTable {{
            background-color: {c.INPUT_BG};
            alternate-background-color: {c.TABLE_ALTERNATE};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 8px;
            gridline-color: {c.BORDER_INPUT};
        }}
        #programsTable::item {{
            padding: 6px 8px;
            background-color: transparent;
            color: {c.TEXT_PRIMARY};
        }}
        #programsTable::item:selected {{
            background-color: {highlight_sel};
            color: {c.TEXT_PRIMARY};
        }}
        #saveProgramsBtn {{
            background-color: {c.cta};
            color: {c.on_cta};
            border: none;
            padding: 8px 22px;
        }}
        #saveProgramsBtn:hover {{
            background-color: {c.cta};
        }}

        /* ============ EmployeeSummaryTab ============ */
        /* Stats cards */
        #statsContainer QFrame {{
            border-radius: 10px;
            padding: 2px;
            min-height: 36px;
        }}
        #statCardBlue {{
            background-color: {c.SURFACE_BG};
            border: 2px solid {primary_hex};
        }}
        #statCardGreen {{
            background-color: {c.SURFACE_BG};
            border: 2px solid {c.SUCCESS};
        }}
        #statCardRed {{
            background-color: {c.SURFACE_BG};
            border: 2px solid {c.ERROR};
        }}
        #statCardYellow {{
            background-color: {c.SURFACE_BG};
            border: 2px solid {c.WARNING};
        }}
        #statCardInfo {{
            background-color: {c.SURFACE_BG};
            border: 2px solid {c.link};
        }}
        #statValue {{
            font-size: 20px;
            font-weight: bold;
            color: {c.TEXT_PRIMARY};
            background-color: transparent;
        }}
        #statValueGreen {{
            font-size: 20px;
            font-weight: bold;
            color: {c.SUCCESS};
            background-color: transparent;
        }}
        #statValueRed {{
            font-size: 20px;
            font-weight: bold;
            color: {c.ERROR};
            background-color: transparent;
        }}
        #statValueYellow {{
            font-size: 20px;
            font-weight: bold;
            color: {c.WARNING};
            background-color: transparent;
        }}
        #statValueInfo {{
            font-size: 16px;
            font-weight: bold;
            color: {c.link};
            background-color: transparent;
        }}
        #statLabel {{
            font-size: 13px;
            font-weight: bold;
            color: {c.TEXT_SECONDARY};
            background-color: transparent;
        }}

        /* Toolbar */
        #toolbarContainer {{
            background-color: transparent;
        }}
        #toolbarPrimaryBtn {{
            background-color: {c.cta};
            color: {c.on_cta};
            border: none;
            border-radius: 6px;
            padding: 7px 16px;
            font-weight: bold;
        }}
        #toolbarPrimaryBtn:hover {{
            background-color: {c.cta};
        }}
        #toolbarBtn {{
            background-color: {c.SURFACE_BG};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 6px;
            padding: 7px 14px;
        }}
        #toolbarBtn:hover {{
            background-color: {highlight_bg};
            border-color: {c.PRIMARY};
        }}
        #toolbarSuccessBtn {{
            background-color: {c.cta};
            color: {c.on_cta};
            border: none;
            border-radius: 6px;
            padding: 7px 16px;
            font-weight: bold;
        }}
        #toolbarSuccessBtn:hover {{
            background-color: {c.SUCCESS};
        }}
        #toolbarPurpleBtn {{
            background-color: {c.dark_btn};
            color: {c.on_dark};
            border: none;
            border-radius: 6px;
            padding: 7px 16px;
            font-weight: bold;
        }}
        #toolbarPurpleBtn:hover {{
            background-color: {c.dark_btn};
        }}
        #toolbarDangerBtn {{
            background-color: transparent;
            color: {c.ERROR};
            border: 1.5px solid {c.ERROR};
            border-radius: 6px;
            padding: 7px 16px;
            font-weight: bold;
        }}
        #toolbarDangerBtn:hover {{
            background-color: {c.ERROR}22;
        }}
        #toolbarDangerBtn:pressed {{
            background-color: {c.ERROR}44;
        }}

        /* Filter panel */
        #filterContainer {{
            background-color: {c.SURFACE_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 8px;
        }}
        #filterContainer QLabel {{
            font-size: 12px;
            color: {c.TEXT_SECONDARY};
            background-color: transparent;
        }}
        #filterCombo {{
            background-color: {c.INPUT_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 6px;
            padding: 4px 10px;
            color: {c.TEXT_PRIMARY};
            min-width: 100px;
        }}
        #filterInput {{
            background-color: {c.INPUT_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 6px;
            padding: 4px 10px;
            color: {c.TEXT_PRIMARY};
            min-width: 140px;
        }}
        #filterCheck {{
            color: {c.TEXT_PRIMARY};
            spacing: 4px;
        }}
        #planBtn {{
            background-color: {c.cta};
            color: {c.on_cta};
            border: none;
            border-radius: 6px;
            padding: 5px 12px;
            font-size: 12px;
        }}
        #planBtn:hover {{
            background-color: {c.cta};
        }}
        #planBtnInfo {{
            background-color: {c.link};
            color: {c.on_dark};
            border: none;
            border-radius: 6px;
            padding: 5px 12px;
            font-size: 12px;
        }}
        #planBtnInfo:hover {{
            background-color: {c.link_hover};
        }}
        #planBtnSuccess {{
            background-color: {c.cta};
            color: {c.on_cta};
            border: none;
            border-radius: 6px;
            padding: 5px 12px;
            font-size: 12px;
        }}
        #planBtnSuccess:hover {{
            background-color: {c.SUCCESS};
        }}

        /* Summary table */
        #summaryTable {{
            background-color: {c.INPUT_BG};
            alternate-background-color: {c.TABLE_ALTERNATE};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 8px;
            gridline-color: {c.BORDER_INPUT};
        }}
        #summaryTable::item {{
            padding: 4px 6px;
            color: {c.TEXT_PRIMARY};
        }}
        #summaryTable::item:selected {{
            background-color: {highlight_sel};
            color: {c.TEXT_PRIMARY};
        }}

        /* Dialog helper buttons */
        #dialogPrimaryBtn {{
            background-color: {c.cta};
            color: {c.on_cta};
            border: none;
            border-radius: 6px;
            padding: 7px 18px;
            font-weight: bold;
        }}
        #dialogDangerBtn {{
            background-color: transparent;
            color: {c.ERROR};
            border: 1.5px solid {c.ERROR};
            border-radius: 6px;
            padding: 7px 18px;
            font-weight: bold;
        }}
        #dialogDangerBtn:hover {{
            background-color: {c.ERROR}22;
        }}

        /* Plan dialog */
        #planExportBtn {{
            background-color: {c.cta};
            color: {c.on_cta};
            border: none;
            border-radius: 6px;
            padding: 7px 18px;
            font-weight: bold;
        }}
        #planCloseBtn {{
            background-color: transparent;
            color: {c.ERROR};
            border: 1.5px solid {c.ERROR};
            border-radius: 6px;
            padding: 7px 18px;
            font-weight: bold;
        }}

        #planStatCard {{
            background-color: {c.SURFACE_BG};
        }}

        /* Context menu */
        #summaryCtxMenu {{
            background-color: {c.MENU_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 6px;
            padding: 4px;
        }}
        #summaryCtxMenu::item {{
            padding: 6px 24px 6px 12px;
            border-radius: 4px;
            color: {c.TEXT_PRIMARY};
        }}
        #summaryCtxMenu::item:selected {{
            background-color: {highlight_bg};
        }}

        /* ============ QLineEdit ============ */
        QLineEdit {{
            background-color: {c.INPUT_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 6px;
            padding: 7px 12px;
            color: {c.TEXT_PRIMARY};
            selection-background-color: {c.selection};
            selection-color: {c.link_hover};
        }}
        QLineEdit:hover {{
            border-color: {c.BORDER_INPUT};
        }}
        QLineEdit:focus {{
            border-color: {c.PRIMARY};
            border-width: 2px;
        }}
        QLineEdit:read-only {{
            background-color: {c.SURFACE_BG};
            color: {c.TEXT_SECONDARY};
        }}
        QLineEdit:disabled {{
            background-color: {c.SURFACE_BG};
            color: {c.TEXT_DISABLED};
            border-color: {c.BORDER_LIGHT};
        }}

        /* ============ QComboBox ============ */
        QComboBox {{
            background-color: {c.INPUT_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 6px;
            padding: 6px 12px;
            color: {c.TEXT_PRIMARY};
            min-height: 20px;
        }}
        QComboBox:hover {{
            border-color: {c.PRIMARY};
        }}
        QComboBox:focus {{
            border-color: {c.PRIMARY};
            border-width: 2px;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {c.SURFACE_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 6px;
            selection-background-color: {highlight_bg};
            selection-color: {c.TEXT_PRIMARY};
            padding: 4px;
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{
            padding: 6px 10px;
            border-radius: 4px;
            color: {c.TEXT_PRIMARY};
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: {highlight_sel};
            color: {c.TEXT_PRIMARY};
        }}

        /* ============ QDateEdit ============ */
        QDateEdit {{
            background-color: {c.INPUT_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 6px;
            padding: 6px 12px;
            color: {c.TEXT_PRIMARY};
            min-height: 20px;
        }}
        QDateEdit:hover {{
            border-color: {c.BORDER_INPUT};
        }}
        QDateEdit:focus {{
            border-color: {c.PRIMARY};
            border-width: 2px;
        }}
        QDateEdit::drop-down {{
            border: none;
            width: 24px;
        }}
        QDateEdit::down-arrow {{
            image: none;
        }}

        /* ============ QSpinBox ============ */
        QSpinBox {{
            background-color: {c.INPUT_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 6px;
            padding: 6px 12px;
            color: {c.TEXT_PRIMARY};
            min-height: 20px;
        }}
        QSpinBox:hover {{
            border-color: {c.BORDER_INPUT};
        }}
        QSpinBox:focus {{
            border-color: {c.PRIMARY};
            border-width: 2px;
        }}

        /* ============ QCheckBox / QRadioButton ============ */
        QCheckBox, QRadioButton {{
            color: {c.TEXT_PRIMARY};
            spacing: 6px;
        }}
        QCheckBox::indicator, QRadioButton::indicator {{
            border: 2px solid {c.BORDER_INPUT};
            border-radius: 3px;
            width: 16px;
            height: 16px;
        }}
        QCheckBox::indicator:hover,
        QRadioButton::indicator:hover {{
            border-color: {c.PRIMARY};
        }}
        QCheckBox::indicator:checked {{
            background-color: {c.cta};
            border-color: {primary_hex};
        }}
        QRadioButton::indicator {{
            border-radius: 9px;
        }}
        QRadioButton::indicator:checked {{
            background-color: {c.cta};
            border-color: {primary_hex};
        }}

        /* ============ QTableWidget ============ */
        QTableWidget {{
            background-color: {c.INPUT_BG};
            alternate-background-color: {c.TABLE_ALTERNATE};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 8px;
            gridline-color: {c.BORDER_INPUT};
            color: {c.TEXT_PRIMARY};
            selection-background-color: {highlight_sel};
            selection-color: {c.TEXT_PRIMARY};
        }}
        QTableWidget::item {{
            padding: 6px 8px;
            background-color: transparent;
            color: {c.TEXT_PRIMARY};
        }}
        QTableWidget::item:selected {{
            background-color: {highlight_sel};
            color: {c.TEXT_PRIMARY};
        }}
        QHeaderView::section {{
            background-color: {c.SURFACE_BG};
            color: {c.PRIMARY};
            padding: 8px 10px;
            border: none;
            border-bottom: 1px solid {c.BORDER_INPUT};
            border-right: 1px solid {c.BORDER_LIGHT};
            font-weight: bold;
            font-size: 12px;
        }}
        QHeaderView::section:first {{
            border-top-left-radius: 8px;
        }}
        QHeaderView::section:last {{
            border-top-right-radius: 8px;
            border-right: none;
        }}
        QHeaderView::section:hover {{
            background-color: {highlight_bg};
        }}

        /* ============ QLabel ============ */
        QLabel {{
            background-color: transparent;
            color: {c.TEXT_PRIMARY};
        }}

        /* ============ QTabWidget / QTabBar ============ */
        QTabWidget::pane {{
            border: none;
            background: transparent;
        }}
        QTabBar::tab {{
            background-color: transparent;
            color: {c.TEXT_SECONDARY};
            padding: 10px 22px;
            border: none;
            border-bottom: 2px solid transparent;
            font-weight: bold;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            color: {c.PRIMARY};
            border-bottom: 2px solid {c.PRIMARY};
            background-color: {highlight_bg};
        }}
        QTabBar::tab:hover:!selected {{
            color: {c.TEXT_PRIMARY};
            border-bottom: 2px solid {c.BORDER_INPUT};
            background-color: {c.surface_subtle};
        }}

        /* ============ QListWidget ============ */
        QListWidget {{
            background-color: {c.INPUT_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 8px;
            color: {c.TEXT_PRIMARY};
        }}
        QListWidget::item {{
            padding: 8px 12px;
            border-radius: 6px;
            color: {c.TEXT_PRIMARY};
        }}
        QListWidget::item:selected {{
            background-color: {highlight_sel};
            color: {c.TEXT_PRIMARY};
        }}
        QListWidget::item:hover {{
            background-color: {highlight_bg};
        }}

        /* ============ QTextEdit / QPlainTextEdit ============ */
        QTextEdit, QPlainTextEdit {{
            background-color: {c.INPUT_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 8px;
            padding: 10px;
            color: {c.TEXT_PRIMARY};
            selection-background-color: {c.selection};
            selection-color: {c.link_hover};
        }}

        /* ============ QScrollBar ============ */
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {c.SCROLLBAR_HANDLE};
            border-radius: 4px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {c.SCROLLBAR_HOVER};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 8px;
            margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {c.SCROLLBAR_HANDLE};
            border-radius: 4px;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {c.SCROLLBAR_HOVER};
        }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            width: 0;
        }}

        /* ============ QMenu / QMenuBar ============ */
        QMenuBar {{
            background-color: {c.MENU_BG};
            border-bottom: 1px solid {c.BORDER_LIGHT};
            color: {c.TEXT_PRIMARY};
        }}
        QMenuBar::item {{
            padding: 6px 14px;
            border-radius: 4px;
            color: {c.TEXT_PRIMARY};
        }}
        QMenuBar::item:selected {{
            background-color: {highlight_bg};
        }}
        QMenu {{
            background-color: {c.MENU_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 8px;
            padding: 6px;
            color: {c.TEXT_PRIMARY};
        }}
        QMenu::item {{
            padding: 7px 24px 7px 14px;
            border-radius: 4px;
            color: {c.TEXT_PRIMARY};
        }}
        QMenu::item:selected {{
            background-color: {highlight_bg};
        }}
        QMenu::item:disabled {{
            color: {c.TEXT_DISABLED};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {c.BORDER_INPUT};
            margin: 4px 8px;
        }}

        /* ============ QToolTip ============ */
        QToolTip {{
            background-color: {c.SURFACE_BG};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QProgressBar {{
            background-color: {c.INPUT_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 4px;
            text-align: center;
            color: {c.TEXT_PRIMARY};
            height: 20px;
        }}
        QProgressBar::chunk {{
            background-color: {c.cta};
            border-radius: 3px;
        }}

        /* ============ QCalendarWidget ============ */
        QCalendarWidget QMenu {{
            background-color: {c.MENU_BG};
        }}
        QCalendarWidget QWidget#qt_calendar_navigationbar {{
            background-color: transparent;
        }}
        QCalendarWidget QToolButton {{
            background-color: transparent;
            border: none;
            color: {c.TEXT_PRIMARY};
            border-radius: 4px;
            padding: 4px;
        }}
        QCalendarWidget QToolButton:hover {{
            background-color: {highlight_bg};
        }}
        QCalendarWidget QSpinBox {{
            background-color: {c.INPUT_BG};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 4px;
            padding: 2px 6px;
            color: {c.TEXT_PRIMARY};
        }}

        /* ============ QMessageBox ============ */
        QMessageBox {{
            background-color: {c.WINDOW_BG};
        }}
        QMessageBox QLabel {{
            color: {c.TEXT_PRIMARY};
            background-color: transparent;
        }}
        QMessageBox QPushButton {{
            min-width: 80px;
        }}
        QMessageBox QPushButton,
        QFileDialog QPushButton,
        QInputDialog QPushButton {{
            background-color: {c.SURFACE_BG};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 8px;
            padding: 6px 18px;
            font-weight: bold;
            min-height: 24px;
        }}
        QMessageBox QPushButton:hover,
        QFileDialog QPushButton:hover,
        QInputDialog QPushButton:hover {{
            background-color: {highlight_bg};
            border-color: {c.PRIMARY};
        }}

        /* ============ Generic QDialog (for custom dialogs) ============ */
        QDialog {{
            background-color: {c.WINDOW_BG};
        }}
        QDialog QLabel {{
            color: {c.TEXT_PRIMARY};
            background-color: transparent;
        }}
        QDialog QLineEdit {{
            color: {c.TEXT_PRIMARY};
        }}

        /* ============ LockDialog ============ */
        #lockCard {{
            background-color: {c.SURFACE_BG};
            border: 1px solid {c.BORDER_LIGHT};
            border-radius: 12px;
        }}
        #lockTitle {{
            font-size: 18px;
            font-weight: bold;
            color: {c.TEXT_PRIMARY};
            background: transparent;
        }}
        #lockDesc {{
            font-size: 13px;
            color: {c.TEXT_SECONDARY};
            background: transparent;
        }}
        #lockPwdInput {{
            font-size: 14px;
            padding: 4px 12px;
            border: 1px solid {c.BORDER_LIGHT};
            border-radius: 4px;
            background-color: {c.INPUT_BG};
            color: {c.TEXT_PRIMARY};
        }}
        #lockPwdInput:focus {{
            border: 1px solid {c.PRIMARY};
        }}
        #lockPwdInput[danger="true"] {{
            border: 2px solid {c.ERROR};
        }}
        #lockExitBtn {{
            background-color: transparent;
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER_LIGHT};
            padding: 8px 16px;
            border-radius: 5px;
            font-size: 13px;
        }}
        #lockExitBtn:hover {{
            background-color: {highlight_bg};
        }}
        #lockUnlockBtn {{
            background-color: {c.SUCCESS};
            color: {c.TEXT_ON_ACCENT};
            border: none;
            padding: 8px 24px;
            border-radius: 5px;
            font-weight: bold;
            font-size: 13px;
        }}
        #lockUnlockBtn:hover {{
            background-color: {c.SUCCESS}dd;
        }}
        #lockUnlockBtn:pressed {{
            background-color: {c.SUCCESS}bb;
        }}

        /* Inline validation message under a field */
        #fieldErrorLabel {{
            color: {c.ERROR};
            background: transparent;
        }}

        /* ============ LockWarningDialog ============ */
        #lockWarningMsg {{
            font-size: 13px;
            color: {c.TEXT_PRIMARY};
            background: transparent;
        }}
        #lockWarningBtn {{
            background-color: {c.PRIMARY};
            color: {c.TEXT_ON_ACCENT};
            border: none;
            padding: 6px 16px;
            border-radius: 4px;
            font-weight: bold;
        }}
        #lockWarningBtn:hover {{
            background-color: {c.PRIMARY}dd;
        }}

        /* ============ AboutDialog ============ */
        #aboutTitleLabel {{
            font-size: 16px;
            font-weight: bold;
            color: {c.PRIMARY};
            background-color: transparent;
        }}
        #aboutVersionLabel {{
            font-size: 12px;
            color: {c.TEXT_SECONDARY};
            background-color: transparent;
        }}
        #aboutDescLabel {{
            font-size: 13px;
            color: {c.TEXT_PRIMARY};
            line-height: 1.6;
            padding: 8px 0;
            background-color: transparent;
        }}
        #aboutInfoWidget {{
            background-color: {c.SURFACE_BG};
            border: 1px solid {c.BORDER_LIGHT};
            border-radius: 10px;
        }}
        #aboutInfoLabel {{
            font-size: 13px;
            color: {c.TEXT_PRIMARY};
            background-color: transparent;
        }}
        #aboutInfoLink {{
            font-size: 13px;
            color: {c.PRIMARY};
            background-color: transparent;
        }}
        #aboutInfoLink:hover {{
            color: {primary_hex};
        }}

        /* ============ Report dialog titles ============ */
        #reportTitleLabel {{
            font-size: 16px;
            font-weight: bold;
            color: {c.PRIMARY};
            padding: 4px 0;
        }}

        /* ============ HelpDialog ============ */
        #helpGroupBox {{
            background-color: {c.SURFACE_BG};
            border: 1px solid {c.BORDER_LIGHT};
            border-radius: 10px;
            margin-top: 14px;
            padding: 18px 16px 16px 16px;
            font-weight: bold;
            font-size: 14px;
            color: {c.PRIMARY};
        }}
        #helpGroupBox::title {{
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 8px;
            color: {c.PRIMARY};
            font-weight: bold;
            font-size: 15px;
        }}
        #helpGroupLabel {{
            font-size: 13px;
            color: {c.TEXT_PRIMARY};
            line-height: 1.5;
            padding: 2px 0;
            background-color: transparent;
        }}
        #helpTocBtn {{
            text-align: left;
            padding: 6px 14px;
            font-size: 12px;
            border: none;
            border-radius: 0;
            color: {c.TEXT_PRIMARY};
            background-color: transparent;
        }}
        #helpTocBtn:hover {{
            background-color: {highlight_bg};
        }}
        #helpTocBtn:pressed {{
            background-color: rgba(128, 128, 128, 50);
        }}
        #helpTocBtn[selected="true"] {{
            background-color: {highlight_bg};
            border-left: 3px solid {c.PRIMARY};
            color: {c.PRIMARY};
            font-weight: bold;
        }}

        /* ============ QFileDialog ============ */
        QFileDialog {{
            background-color: {c.WINDOW_BG};
        }}
        QFileDialog QLabel {{
            color: {c.TEXT_PRIMARY};
            background-color: transparent;
        }}
        QFileDialog QListView,
        QFileDialog QTreeView {{
            background-color: {c.INPUT_BG};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 6px;
        }}

        /* ============ QInputDialog ============ */
        QInputDialog {{
            background-color: {c.WINDOW_BG};
        }}
        QInputDialog QLabel {{
            color: {c.TEXT_PRIMARY};
            background-color: transparent;
        }}

        /* ============ Dialog children fallback ============ */
        QDialog QTableWidget {{
            background-color: {c.INPUT_BG};
            alternate-background-color: {c.TABLE_ALTERNATE};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 8px;
            gridline-color: {c.BORDER_INPUT};
        }}
        QDialog QTableWidget::item {{
            background-color: transparent;
            color: {c.TEXT_PRIMARY};
        }}
        QDialog QTableWidget::item:selected {{
            background-color: {highlight_sel};
            color: {c.TEXT_PRIMARY};
        }}
        QDialog QListWidget {{
            background-color: {c.INPUT_BG};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 8px;
        }}
        QDialog QListWidget::item {{
            color: {c.TEXT_PRIMARY};
        }}
        QDialog QListWidget::item:selected {{
            background-color: {highlight_sel};
            color: {c.TEXT_PRIMARY};
        }}
        QDialog QTextEdit,
        QDialog QLineEdit {{
            background-color: {c.INPUT_BG};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 6px;
            padding: 7px 12px;
        }}
        QDialog QLineEdit:hover,
        QDialog QComboBox:hover {{
            border-color: {c.BORDER_INPUT};
        }}
        QDialog QComboBox {{
            background-color: {c.INPUT_BG};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.BORDER_INPUT};
            border-radius: 6px;
            padding: 6px 12px;
        }}

        /* ============ Tables: hover, header, sorting polish ============ */
        QTableView, QTableWidget {{
            gridline-color: {c.BORDER_LIGHT};
            selection-background-color: {c.HIGHLIGHT_SELECTED};
            selection-color: {c.TEXT_PRIMARY};
        }}
        QTableView::item, QTableWidget::item {{
            padding: 2px 6px;
        }}
        QTableView::item:hover, QTableWidget::item:hover {{
            background-color: {c.HIGHLIGHT_BG};
        }}
        QHeaderView::section {{
            background-color: {c.SURFACE_BG};
            color: {c.TEXT_SECONDARY};
            padding: 6px 10px;
            border: none;
            border-bottom: 2px solid {c.BORDER_LIGHT};
            border-right: 1px solid {c.BORDER_LIGHT};
            font-weight: bold;
        }}
        QHeaderView::section:hover {{
            color: {c.PRIMARY};
        }}
        /* ============ Empty-state placeholder ============ */
        QLabel#tableEmptyState {{
            color: {c.TEXT_SECONDARY};
            font-size: 14px;
            background: transparent;
        }}
        /* ============ Field state markers (theme-aware) ============ */
        QLineEdit[fieldState="invalid"], QComboBox[fieldState="invalid"],
        QPlainTextEdit[fieldState="invalid"], QTextEdit[fieldState="invalid"],
        QListWidget[fieldState="invalid"] {{
            border: 2px solid {c.ERROR};
        }}
        QLineEdit[fieldState="warning"], QComboBox[fieldState="warning"] {{
            border: 2px solid {c.WARNING};
        }}

        /* ============ QStatusBar ============ */
        QStatusBar {{
            background-color: {c.SURFACE_BG};
            border-top: 1px solid {c.BORDER_LIGHT};
            color: {c.TEXT_SECONDARY};
            font-size: 12px;
            padding: 2px 8px;
        }}
        QStatusBar::item {{
            border: none;
        }}

        /* ============ Каркас окна: боковое меню, шапка страницы ============ */
        #sidebar {{
            background-color: {c.side_bg};
        }}
        #sidebar QLabel {{
            background: transparent;
        }}
        #sidebarLogo {{
            background-color: #FFFFFF;
            border-radius: 10px;
        }}
        #sidebarTitle {{
            color: {c.side_strong};
            font-family: "Space Grotesk", "Rubik", "Segoe UI", sans-serif;
            font-size: 15px;
            font-weight: 600;
        }}
        #sidebarMuted {{
            color: {c.side_muted};
            font-size: 12px;
        }}
        #sidebarSection {{
            color: {c.side_muted};
            font-size: 11px;
            font-weight: 600;
            padding: 8px 10px 4px 10px;
        }}
        #sidebarToday #sidebarSection {{
            padding: 0;
        }}
        #sidebarLine {{
            background-color: {c.side_line};
            border: none;
        }}
        #sidebarOrg {{
            background-color: {c.side_btn};
            color: {c.side_strong};
            border: 1px solid {c.side_line};
            border-radius: 8px;
            padding: 8px 10px;
            text-align: left;
            font-size: 12px;
            font-weight: 500;
        }}
        #sidebarOrg::menu-indicator {{
            subcontrol-position: right center;
            right: 8px;
        }}
        #sidebarOrg:hover {{
            border-color: {c.side_muted};
            background-color: {c.side_btn};
        }}
        #sidebarItem, #sidebarBottom {{
            background-color: transparent;
            color: {c.side_text};
            border: none;
            border-radius: 8px;
            padding: 0 4px 0 6px;
            text-align: left;
            font-size: 12px;
            font-weight: 500;
        }}
        #sidebarItem:hover, #sidebarBottom:hover {{
            background-color: {c.side_btn};
            color: {c.side_strong};
        }}
        #sidebarItem:checked {{
            background-color: {c.side_active_bg};
            color: {c.side_active_fg};
            font-weight: 600;
        }}
        #sidebarToday {{
            background-color: {c.side_btn};
            border: 1px solid {c.side_line};
            border-radius: 10px;
        }}
        #sidebarClock {{
            color: {c.side_strong};
            font-family: "Space Grotesk", "Rubik", "Segoe UI", sans-serif;
            font-size: 26px;
            font-weight: 600;
        }}
        #sidebarCount {{
            color: {c.side_strong};
            font-weight: 600;
        }}
        #pageHeader {{
            background-color: {c.surface};
            border-bottom: 1px solid {c.border};
        }}
        #pageTitle {{
            color: {c.text};
            font-family: "Space Grotesk", "Rubik", "Segoe UI", sans-serif;
            font-size: 21px;
            font-weight: 600;
            background: transparent;
        }}
        #pageSubtitle {{
            color: {c.text_muted};
            font-size: 12px;
            background: transparent;
        }}
        #settingsSections {{
            background-color: {c.surface_subtle};
            border: 1px solid {c.border};
            border-radius: 10px;
            padding: 6px;
            outline: none;
        }}
        #settingsSections::item {{
            padding: 8px 10px;
            border-radius: 8px;
            color: {c.text_secondary};
        }}
        #settingsSections::item:selected {{
            background-color: {c.selection};
            color: {c.link_hover};
        }}
        #settingsSectionTitle {{
            font-family: "Space Grotesk", "Rubik", "Segoe UI", sans-serif;
            font-size: 16px;
            font-weight: 600;
        }}
        #settingsHint {{
            color: {c.text_muted};
        }}
        #themeCard {{
            background-color: {c.surface};
            border: 2px solid {c.border};
            border-radius: 10px;
        }}
        #themeCard:checked {{
            border-color: {c.link};
        }}
        #themeCard:hover {{
            border-color: {c.link};
            background-color: {c.surface};
        }}
        #themeCardName {{
            background: transparent;
            font-weight: 600;
        }}
    """


# ============ ШРИФТЫ ============

def load_app_fonts(fonts_dir: str) -> list:
    """Регистрирует встроенные шрифты (Rubik, Space Grotesk, OFL 1.1) из fonts_dir.

    Отсутствие файлов не ошибка: QSS содержит запасные семейства.
    Возвращает список семейств, которые удалось загрузить."""
    from PySide6.QtGui import QFontDatabase
    families = []
    if not os.path.isdir(fonts_dir):
        return families
    for name in sorted(os.listdir(fonts_dir)):
        if not name.lower().endswith((".ttf", ".otf")):
            continue
        font_id = QFontDatabase.addApplicationFont(os.path.join(fonts_dir, name))
        if font_id < 0:
            logger.debug("Font not loaded: %s", name)
            continue
        families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return families


# ============ MICA BACKDROP ============

def apply_mica(window) -> bool:
    """
    Применяет Mica backdrop к окну (Windows 11+).
    БЕЗ прозрачности — просто Mica + корректные цвета рамки.
    """
    if sys.platform != "win32":
        return False

    try:
        hwnd = int(window.winId())
        dwmapi = ctypes.windll.dwmapi

        DWMWA_SYSTEMBACKDROP_TYPE = 38
        DWMSBT_MAINWINDOW = 2

        attr = ctypes.c_int(DWMSBT_MAINWINDOW)
        result = dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_SYSTEMBACKDROP_TYPE,
            ctypes.byref(attr),
            ctypes.sizeof(attr)
        )

        if result == 0:
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            dark_mode = ctypes.c_int(0)
            dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(dark_mode),
                ctypes.sizeof(dark_mode)
            )
            return True

        return False

    except (AttributeError, ValueError, OSError, ctypes.ArgumentError):
        logger.debug("Mica not supported on this system")
        return False


# ============ THEME MANAGER ============

def get_theme_dir(base_dir: str) -> str:
    """Дирекория для файла настроек темы."""
    d = os.path.join(base_dir, "data")
    os.makedirs(d, exist_ok=True)
    return d


def get_theme_file(base_dir: str) -> str:
    """Путь к файлу настроек темы."""
    return os.path.join(get_theme_dir(base_dir), "theme_settings.json")


def load_theme(base_dir: str) -> str:
    """Загрузка темы; старые ключи (light/dark/dracula/monokai) переводятся в новые."""
    path = get_theme_file(base_dir)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return normalize_theme(data.get('theme', DEFAULT_THEME))
        except (OSError, json.JSONDecodeError) as e:
            logger.debug("Failed to load theme: %s", e)
    return DEFAULT_THEME


def save_theme(base_dir: str, theme: str):
    """Сохранение темы."""
    path = get_theme_file(base_dir)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'theme': normalize_theme(theme)}, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.debug("Failed to save theme: %s", e)


# ============ GLASS CARD & PILL BUTTON ============

from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class GlassCard(QFrame):
    """Glass-карточка с acrylic-эффектом (имитация через полупрозрачность)."""

    def __init__(self, parent=None, title: str = "", elevation: int = 1):
        super().__init__(parent)
        self._title = title
        self._elevation = elevation
        self._init_ui()

    def _init_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid rgba(74, 144, 226, 0.15);
                border-radius: 12px;
            }
        """)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)

        if self._title:
            title_label = QLabel(self._title)
            title_label.setStyleSheet("""
                color: #4A90E2;
                font-weight: bold;
                font-size: 15px;
            """)
            self._layout.insertWidget(0, title_label)

    def layout(self):
        return self._layout


class PillButton(QPushButton):
    """Скруглённая кнопка с анимацией нажатия."""

    def __init__(self, text: str = "", variant: str = "default", parent=None):
        super().__init__(text, parent)
        self._variant = variant
        self._apply_style()

    def _apply_style(self):
        if self._variant == "primary":
            self.setProperty("primary", True)
        elif self._variant == "success":
            self.setProperty("success", True)
        elif self._variant == "danger":
            self.setProperty("danger", True)
        self.style().unpolish(self)
        self.style().polish(self)
