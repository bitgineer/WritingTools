"""Stacked original and reworked text for substantial rewrites."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from rework.model import Rework
from rework.theme import Palette


class FullTextView(QtWidgets.QTextEdit):
    def __init__(self, rework: Rework, palette: Palette, parent=None):
        super().__init__(parent)
        self.setObjectName("diff")
        self.setReadOnly(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.document().setDocumentMargin(10)
        self.setAccessibleName("Original and reworked text")

        font = QtGui.QFont()
        font.setFamilies(["Segoe UI", "Inter", "Ubuntu", "sans-serif"])
        font.setPixelSize(13)
        self.setFont(font)

        self._build(rework, palette)

    def _build(self, rework: Rework, palette: Palette) -> None:
        cursor = self.textCursor()
        cursor.beginEditBlock()

        label_font = QtGui.QFont(self.font())
        label_font.setPixelSize(10)
        label_font.setBold(True)
        label_fmt = QtGui.QTextCharFormat()
        label_fmt.setFont(label_font)
        label_fmt.setForeground(QtGui.QColor(palette.muted))

        body_fmt = QtGui.QTextCharFormat()
        body_fmt.setFont(self.font())
        body_fmt.setForeground(QtGui.QColor(palette.ink))

        spacing = QtGui.QTextBlockFormat()
        spacing.setTopMargin(8)
        spacing.setBottomMargin(8)

        cursor.insertText("ORIGINAL", label_fmt)
        cursor.insertBlock(spacing)
        cursor.insertText(rework.original, body_fmt)
        cursor.insertBlock(spacing)
        cursor.insertText("REWORKED", label_fmt)
        cursor.insertBlock(spacing)
        cursor.insertText(rework.revised, body_fmt)

        cursor.endEditBlock()

        line_height = QtGui.QTextBlockFormat()
        line_height.setLineHeight(145, QtGui.QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        cursor.select(QtGui.QTextCursor.SelectionType.Document)
        cursor.mergeBlockFormat(line_height)
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)
        self.setTextCursor(cursor)
        self.verticalScrollBar().setValue(0)

    def fit_to_content(self, max_height: int = 320) -> None:
        width = self.viewport().width()
        if width <= 0:
            return
        self.document().setTextWidth(width)
        height = int(self.document().size().height()) + 2 * int(self.document().documentMargin())
        self.setFixedHeight(max(96, min(max_height, height + 2)))
