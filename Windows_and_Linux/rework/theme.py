"""Tokens for the rework receipt.

The receipt has its own small system rather than inheriting the popup's
inline colors and PNG backgrounds. Later surfaces can adopt the same tokens.
"""

from __future__ import annotations

from dataclasses import dataclass

import darkdetect


@dataclass(frozen=True)
class Palette:
    mode: str
    surface: str
    surface_alt: str
    ink: str
    muted: str
    hairline: str
    accent: str
    accent_hover: str
    accent_text: str
    accent_soft: str
    delete_fg: str
    delete_bg: str
    insert_fg: str
    insert_bg: str
    shadow: str


LIGHT = Palette(
    mode="light",
    surface="#FFFFFF",
    surface_alt="#F1F2EE",
    ink="#1E2320",
    muted="#5F6661",
    hairline="#E2E5DF",
    accent="#2E6B4F",
    accent_hover="#255840",
    accent_text="#FFFFFF",
    accent_soft="#E7F1EB",
    delete_fg="#9F2D24",
    delete_bg="#FBEAE7",
    insert_fg="#1F6B45",
    insert_bg="#E4F3EA",
    shadow="#40000000",
)

DARK = Palette(
    mode="dark",
    surface="#232522",
    surface_alt="#2D302C",
    ink="#F1F2EE",
    muted="#A2A8A1",
    hairline="#383B36",
    accent="#8AC7A6",
    accent_hover="#A5D8BC",
    accent_text="#191A18",
    accent_soft="#253A2E",
    delete_fg="#F3A39B",
    delete_bg="#3A2522",
    insert_fg="#9ADBB8",
    insert_bg="#22382B",
    shadow="#80000000",
)


def current_palette() -> Palette:
    return DARK if darkdetect.isDark() else LIGHT


def history_stylesheet(p: Palette) -> str:
    return card_stylesheet(p) + f"""
        QWidget#historyRoot {{
            background-color: {p.surface_alt};
        }}
        QLabel#historyTitle {{
            color: {p.ink};
            font-size: 20px;
            font-weight: 700;
        }}
        QLabel#historyCount, QLabel#historyMeta, QLabel#historyPrivacy {{
            color: {p.muted};
            font-size: 12px;
        }}
        QLabel#historySection {{
            color: {p.muted};
            font-size: 10px;
            font-weight: 700;
        }}
        QFrame#historyPanel {{
            background-color: {p.surface};
            border: 1px solid {p.hairline};
            border-radius: 12px;
        }}
        QFrame#historyTextPanel {{
            background-color: {p.surface_alt};
            border: none;
            border-radius: 8px;
        }}
        QLineEdit#historySearch {{
            background-color: {p.surface};
            color: {p.ink};
            border: 1px solid {p.hairline};
            border-radius: 8px;
            padding: 7px 10px;
            font-size: 13px;
            outline: none;
        }}
        QLineEdit#historySearch:focus {{
            border: 1px solid {p.accent};
        }}
        QSplitter::handle {{
            background-color: {p.hairline};
        }}
        QSplitter::handle:horizontal {{
            width: 1px;
        }}
        QSplitter::handle:vertical {{
            height: 1px;
        }}
        QListWidget#historyList {{
            background-color: transparent;
            border: none;
            padding: 2px;
        }}
        QListWidget#historyList:focus {{
            border: 1px solid {p.accent};
            border-radius: 8px;
        }}
        QListWidget#historyList::item {{
            color: {p.ink};
            padding: 9px 10px;
            border-radius: 8px;
        }}
        QListWidget#historyList::item:hover {{
            background-color: {p.surface_alt};
        }}
        QListWidget#historyList::item:selected {{
            background-color: {p.accent};
            color: {p.accent_text};
        }}
        QTextBrowser#historyText {{
            background-color: transparent;
            border: none;
            color: {p.ink};
            font-size: 13px;
        }}
        QPushButton#historyToggle {{
            background-color: transparent;
            color: {p.muted};
            border: 1px solid {p.hairline};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 12px;
        }}
        QPushButton#historyToggle:hover {{
            background-color: {p.surface_alt};
            color: {p.ink};
        }}
        QPushButton#historyToggle:checked {{
            background-color: {p.accent_soft};
            color: {p.ink};
            border-color: {p.accent};
        }}
        QPushButton#danger {{
            background-color: transparent;
            color: {p.delete_fg};
            border: 1px solid transparent;
        }}
        QPushButton#danger:hover {{
            background-color: {p.delete_bg};
        }}
        QPushButton#danger:focus, QPushButton#historyToggle:focus {{
            border: 2px solid {p.accent};
        }}
        QPushButton#ghost:disabled, QPushButton#danger:disabled {{
            background-color: transparent;
            color: {p.muted};
        }}
    """


def card_stylesheet(p: Palette) -> str:
    return f"""
        QFrame#card {{
            background-color: {p.surface};
            border: 1px solid {p.hairline};
            border-radius: 12px;
        }}
        QLabel {{
            color: {p.ink};
            font-family: "Segoe UI", "Inter", "Ubuntu", sans-serif;
            font-size: 13px;
            background: transparent;
        }}
        QLabel#eyebrow {{
            color: {p.muted};
            font-size: 10px;
            font-weight: 700;
        }}
        QLabel#title {{
            color: {p.ink};
            font-size: 14px;
            font-weight: 600;
        }}
        QLabel#headline {{
            color: {p.ink};
            font-size: 13px;
        }}
        QLabel#sample {{
            color: {p.muted};
            font-size: 12px;
        }}
        QLabel#meta, QLabel#hint {{
            color: {p.muted};
            font-size: 12px;
        }}
        QLabel#privacy {{
            color: {p.muted};
            font-size: 11px;
        }}
        QFrame#divider {{
            background-color: {p.hairline};
            border: none;
            max-height: 1px;
            min-height: 1px;
        }}
        QPushButton {{
            font-family: "Segoe UI", "Inter", "Ubuntu", sans-serif;
            font-size: 12px;
            border-radius: 8px;
            padding: 7px 12px;
        }}
        QPushButton#primary {{
            background-color: {p.accent};
            color: {p.accent_text};
            border: 1px solid {p.accent};
            font-weight: 600;
        }}
        QPushButton#primary:hover {{
            background-color: {p.accent_hover};
            border-color: {p.accent_hover};
        }}
        QPushButton#ghost {{
            background-color: transparent;
            color: {p.muted};
            border: 1px solid transparent;
        }}
        QPushButton#ghost:hover {{
            background-color: {p.surface_alt};
            color: {p.ink};
        }}
        QToolButton#close {{
            background-color: transparent;
            color: {p.muted};
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            padding: 0px;
        }}
        QToolButton#close:hover {{
            background-color: {p.surface_alt};
            color: {p.ink};
        }}
        QPushButton#icon {{
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 6px;
            padding: 0px;
        }}
        QPushButton#icon:hover {{
            background-color: {p.surface_alt};
        }}
        QPushButton#icon:focus {{
            border: 1px solid {p.accent};
        }}
        QTextEdit#diff {{
            background-color: transparent;
            border: none;
            color: {p.ink};
            selection-background-color: {p.accent_soft};
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {p.hairline};
            border-radius: 4px;
            min-height: 24px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """
