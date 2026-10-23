"""Application-wide design system for the paper theme.

The receipt and history surfaces established the language. This module makes
it available to every window: warm paper, ink text, one forest accent, thin
hairlines, and a single set of control styles.

The app follows the system light/dark mode. There is no gradient theme.
"""

from __future__ import annotations

import os
import sys
from typing import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from rework.theme import DARK, LIGHT, Palette, current_palette

FONT_STACK = '"Segoe UI", "Inter", "Ubuntu", sans-serif'
SERIF_STACK = 'Georgia, "Iowan Old Style", "Palatino Linotype", serif'

PAGE_MARGIN = 28
CARD_PADDING = 20
GAP = 12


def apply_app_style(app: QtWidgets.QApplication) -> Palette:
    """Apply the shared stylesheet, palette, and font to the whole app."""
    p = current_palette()
    app.setStyleSheet(app_stylesheet(p))

    qt_palette = app.palette()
    qt_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(p.surface_alt))
    qt_palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(p.ink))
    qt_palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(p.surface))
    qt_palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(p.ink))
    qt_palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(p.surface))
    qt_palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(p.ink))
    qt_palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(p.accent))
    qt_palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(p.accent_text))
    qt_palette.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor(p.accent))
    qt_palette.setColor(QtGui.QPalette.ColorRole.LinkVisited, QtGui.QColor(p.accent))
    app.setPalette(qt_palette)

    font = QtGui.QFont()
    font.setFamilies(["Segoe UI", "Inter", "Ubuntu", "sans-serif"])
    font.setPixelSize(13)
    app.setFont(font)
    return p


def app_stylesheet(p: Palette) -> str:
    return f"""
        QWidget {{
            color: {p.ink};
            font-family: {FONT_STACK};
            font-size: 13px;
        }}
        QMainWindow, QDialog, QWidget#AppPage {{
            background-color: {p.surface_alt};
        }}
        QLabel {{
            background: transparent;
        }}
        QLabel#PageTitle {{
            color: {p.ink};
            font-size: 20px;
            font-weight: 700;
        }}
        QLabel#hero {{
            color: {p.ink};
            font-size: 28px;
            font-weight: 700;
        }}
        QLabel#lead {{
            color: {p.ink};
            font-size: 14px;
        }}
        QLabel#badge {{
            background-color: {p.accent_soft};
            color: {p.accent};
            border-radius: 14px;
            font-size: 13px;
            font-weight: 700;
        }}
        QLabel#PageSubtitle {{
            color: {p.muted};
            font-size: 13px;
        }}
        QLabel#SectionTitle {{
            color: {p.ink};
            font-size: 14px;
            font-weight: 600;
        }}
        QLabel#FieldLabel {{
            color: {p.muted};
            font-size: 12px;
            font-weight: 600;
        }}
        QLabel#Meta, QLabel#Hint {{
            color: {p.muted};
            font-size: 12px;
        }}
        QFrame#Card, QFrame#SectionCard {{
            background-color: {p.surface};
            border: 1px solid {p.hairline};
            border-radius: 12px;
        }}
        QFrame#UserMessage {{
            background-color: {p.accent_soft};
            border: none;
            border-radius: 10px;
        }}
        QTextBrowser#prose {{
            background-color: transparent;
            border: none;
            padding: 0px;
            color: {p.ink};
            selection-background-color: {p.accent_soft};
            selection-color: {p.ink};
        }}
        QFrame#Divider {{
            background-color: {p.hairline};
            border: none;
            max-height: 1px;
            min-height: 1px;
        }}
        QPushButton {{
            background-color: {p.surface};
            color: {p.ink};
            border: 1px solid {p.hairline};
            border-radius: 8px;
            padding: 7px 12px;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {p.surface_alt};
        }}
        QPushButton:pressed {{
            background-color: {p.accent_soft};
        }}
        QPushButton:focus {{
            border: 2px solid {p.accent};
        }}
        QPushButton:disabled {{
            background-color: {p.surface_alt};
            color: {p.muted};
        }}
        QPushButton#primary {{
            background-color: {p.accent};
            color: {p.accent_text};
            border-color: {p.accent};
            font-weight: 600;
        }}
        QPushButton#primary:hover {{
            background-color: {p.accent_hover};
            border-color: {p.accent_hover};
        }}
        QPushButton#primary:focus {{
            border: 2px solid {p.accent_text};
        }}
        QPushButton#ghost {{
            background-color: transparent;
            color: {p.muted};
            border-color: transparent;
        }}
        QPushButton#link {{
            background-color: transparent;
            color: {p.accent};
            border: none;
            padding: 2px 0px;
            text-decoration: underline;
        }}
        QPushButton#link:hover {{
            color: {p.accent_hover};
        }}
        QPushButton#link:focus {{
            border: 2px solid {p.accent};
        }}
        QPushButton#ghost:hover {{
            background-color: {p.surface_alt};
            color: {p.ink};
        }}
        QPushButton#ghost:disabled {{
            background-color: transparent;
            color: {p.muted};
        }}
        QPushButton#danger {{
            background-color: transparent;
            color: {p.delete_fg};
            border-color: transparent;
        }}
        QPushButton#danger:hover {{
            background-color: {p.delete_bg};
        }}
        QPushButton#danger:disabled {{
            background-color: transparent;
            color: {p.muted};
        }}
        QPushButton#segment {{
            background-color: transparent;
            color: {p.muted};
            border: 1px solid {p.hairline};
            padding: 6px 12px;
            border-radius: 7px;
        }}
        QPushButton#segment:checked {{
            background-color: {p.accent_soft};
            color: {p.ink};
            border-color: {p.accent};
        }}
        QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {{
            background-color: {p.surface};
            color: {p.ink};
            border: 1px solid {p.hairline};
            border-radius: 8px;
            padding: 7px 10px;
            selection-background-color: {p.accent_soft};
            selection-color: {p.ink};
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
        QTextEdit:focus, QPlainTextEdit:focus {{
            border-color: {p.accent};
        }}
        QLineEdit:disabled, QComboBox:disabled {{
            background-color: {p.surface_alt};
            color: {p.muted};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 22px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {p.surface};
            color: {p.ink};
            border: 1px solid {p.hairline};
            selection-background-color: {p.accent_soft};
            selection-color: {p.ink};
        }}
        QCheckBox, QRadioButton {{
            color: {p.ink};
            spacing: 7px;
        }}
        QScrollArea {{
            background: transparent;
            border: none;
        }}
        QScrollArea > QWidget > QWidget {{
            background: transparent;
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
        QMenu {{
            background-color: {p.surface};
            color: {p.ink};
            border: 1px solid {p.hairline};
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 20px 6px 10px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {p.accent_soft};
            color: {p.ink};
        }}
        QToolTip {{
            background-color: {p.ink};
            color: {p.surface};
            border: none;
            padding: 4px 6px;
        }}
        QMessageBox {{
            background-color: {p.surface};
        }}
        QListWidget, QTableWidget {{
            background-color: {p.surface};
            color: {p.ink};
            border: 1px solid {p.hairline};
            border-radius: 8px;
        }}
    """


def popup_stylesheet(p: Palette) -> str:
    return f"""
        QWidget {{
            color: {p.ink};
            font-family: {FONT_STACK};
            font-size: 13px;
        }}
        QLabel#popupTitle {{
            color: {p.ink};
            font-size: 14px;
            font-weight: 600;
        }}
        QLabel#popupSubtitle, QLabel#popupHint {{
            color: {p.muted};
            font-size: 12px;
        }}
        QLineEdit#popupInput {{
            background-color: {p.surface};
            color: {p.ink};
            border: 1px solid {p.hairline};
            border-radius: 8px;
            padding: 8px 10px;
            font-size: 13px;
        }}
        QLineEdit#popupInput:focus {{
            border-color: {p.accent};
        }}
        QPushButton#actionButton {{
            background-color: {p.surface};
            color: {p.ink};
            border: 1px solid {p.hairline};
            border-radius: 8px;
            padding: 8px 10px;
            text-align: left;
            font-size: 13px;
        }}
        QPushButton#actionButton:hover {{
            background-color: {p.accent_soft};
            border-color: {p.accent};
        }}
        QPushButton#actionButton:focus {{
            border: 2px solid {p.accent};
        }}
        QPushButton#actionButton[dragging="true"] {{
            border: 2px dashed {p.accent};
        }}
        QPushButton#addButton {{
            background-color: transparent;
            color: {p.muted};
            border: 1px dashed {p.hairline};
            border-radius: 8px;
            padding: 9px;
            font-size: 12px;
        }}
        QPushButton#addButton:hover {{
            background-color: {p.surface_alt};
            color: {p.ink};
            border-color: {p.accent};
        }}
        QPushButton#addButton:focus {{
            border: 2px solid {p.accent};
        }}
        QPushButton#popupIcon, QPushButton#popupClose {{
            background-color: transparent;
            color: {p.muted};
            border: none;
            border-radius: 6px;
            font-size: 17px;
            padding: 0px;
        }}
        QPushButton#popupIcon:hover, QPushButton#popupClose:hover {{
            background-color: {p.surface_alt};
            color: {p.ink};
        }}
        QPushButton#popupIcon:focus, QPushButton#popupClose:focus {{
            border: 2px solid {p.accent};
        }}
        QPushButton#send {{
            background-color: {p.accent};
            border: 1px solid {p.accent};
            border-radius: 8px;
            padding: 0px;
        }}
        QPushButton#send:hover {{
            background-color: {p.accent_hover};
            border-color: {p.accent_hover};
        }}
        QPushButton#send:focus {{
            border: 2px solid {p.accent_text};
        }}
        QPushButton#overlay {{
            background-color: {p.surface};
            border: 1px solid {p.hairline};
            border-radius: 9px;
            padding: 0px;
        }}
        QPushButton#overlay:hover {{
            background-color: {p.accent_soft};
        }}
        QPushButton#overlay:focus {{
            border: 2px solid {p.accent};
        }}
    """


def icon(name: str, p: Palette | None = None) -> QtGui.QIcon | None:
    p = p or current_palette()
    path = os.path.join(
        os.path.dirname(sys.argv[0]),
        "icons",
        name + ("_dark" if p.mode == "dark" else "_light") + ".png",
    )
    return QtGui.QIcon(path) if os.path.exists(path) else None


def clock_icon(p: Palette | None = None, size: int = 16) -> QtGui.QIcon:
    """A hairline clock for History actions.

    Drawn in code so it follows the light and dark palettes without a PNG per
    theme and without a build step.
    """
    p = p or current_palette()
    scale = 2
    pixmap = QtGui.QPixmap(size * scale, size * scale)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)

    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
    pen = QtGui.QPen(QtGui.QColor(p.muted))
    pen.setWidthF(1.4)
    painter.setPen(pen)

    inset = 2.0
    painter.drawEllipse(
        QtCore.QRectF(inset, inset, size - inset * 2, size - inset * 2)
    )
    center = QtCore.QPointF(size / 2, size / 2)
    painter.drawLine(center, QtCore.QPointF(size / 2, 4.2))
    painter.drawLine(center, QtCore.QPointF(size - 5.0, size / 2 + 1.6))
    painter.end()
    return QtGui.QIcon(pixmap)


def page_header(title: str, subtitle: str | None = None) -> QtWidgets.QWidget:
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    title_label = QtWidgets.QLabel(title)
    title_label.setObjectName("PageTitle")
    layout.addWidget(title_label)

    if subtitle:
        subtitle_label = QtWidgets.QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)

    return widget


def section_card(
    title: str | None = None,
    subtitle: str | None = None,
) -> tuple[QtWidgets.QFrame, QtWidgets.QVBoxLayout]:
    frame = QtWidgets.QFrame()
    frame.setObjectName("SectionCard")
    layout = QtWidgets.QVBoxLayout(frame)
    layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
    layout.setSpacing(GAP)

    if title:
        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("SectionTitle")
        layout.addWidget(title_label)

    if subtitle:
        subtitle_label = QtWidgets.QLabel(subtitle)
        subtitle_label.setObjectName("Meta")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)

    return frame, layout


def field_label(text: str) -> QtWidgets.QLabel:
    label = QtWidgets.QLabel(text)
    label.setObjectName("FieldLabel")
    return label


def divider() -> QtWidgets.QFrame:
    line = QtWidgets.QFrame()
    line.setObjectName("Divider")
    line.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    return line


def primary_button(text: str, icon_name: str | None = None) -> QtWidgets.QPushButton:
    button = QtWidgets.QPushButton(text)
    button.setObjectName("primary")
    button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(32)
    if icon_name:
        button.setIcon(icon(icon_name))
    return button


def ghost_button(text: str, icon_name: str | None = None) -> QtWidgets.QPushButton:
    button = QtWidgets.QPushButton(text)
    button.setObjectName("ghost")
    button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(32)
    if icon_name:
        button.setIcon(icon(icon_name))
    return button


def danger_button(text: str) -> QtWidgets.QPushButton:
    button = QtWidgets.QPushButton(text)
    button.setObjectName("danger")
    button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(32)
    return button


def segmented_control(
    options: list[tuple[str, str]],
    current: str,
    on_change: Callable[[str], None],
) -> tuple[QtWidgets.QWidget, dict[str, QtWidgets.QPushButton]]:
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    group = QtWidgets.QButtonGroup(widget)
    group.setExclusive(True)
    buttons: dict[str, QtWidgets.QPushButton] = {}

    for key, label in options:
        button = QtWidgets.QPushButton(label)
        button.setObjectName("segment")
        button.setCheckable(True)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.setChecked(key == current)
        group.addButton(button)
        layout.addWidget(button)
        buttons[key] = button
        button.clicked.connect(lambda _=False, k=key: on_change(k))

    layout.addStretch()
    return widget, buttons
